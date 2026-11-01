"""Snowpark Python stored procedure handlers.

Deployed by the Snowflake CLI from snowpark/snowflake.yml into <database>.OPS:

    GENERATE_DATA(days, seed)            refresh the synthetic RAW tables
    COMPUTE_CUSTOMER_HEALTH()            0-100 health score per customer (Snowpark DataFrame API)
    RUN_AGENT_EVAL(agent_fqn)            run the agent eval set and store every result

Each handler's first argument is the Snowpark Session Snowflake passes in. The procedures run with
owner's rights (the default), so they act as NOI_DBT_DEV / NOI_DBT_PROD, which own the data.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import date

from snowflake.snowpark import Session
from snowflake.snowpark import functions as F

from noi_snowpark import agent_eval
from noi_snowpark.generate_data import generate_tables, write_to_snowflake


def _current_database(session: Session) -> str:
    return session.get_current_database().strip('"')


# --------------------------------------------------------------------------
# 1. GENERATE_DATA: the same generator code you run locally
# --------------------------------------------------------------------------
def generate_data(session: Session, days: int, seed: int) -> str:
    db = _current_database(session)
    tables = generate_tables(date.today(), days, seed)
    counts = write_to_snowflake(session, tables, database=db, schema="RAW")
    return json.dumps({"database": db, "as_of": str(date.today()), "rows": counts})


# --------------------------------------------------------------------------
# 2. COMPUTE_CUSTOMER_HEALTH: Snowpark DataFrame API, computed where the data lives
# --------------------------------------------------------------------------
# Scoring rules (documented here, applied in build_health_frame):
#   start at 100, then subtract
#     uptime:    10 points per percentage point below 100 (7-day average), at most 40
#     roaming:   5 points per daily roaming failure above 2 per AP (7-day average), at most 25
#     cases:     10 points per open critical (P1/P2) case, at most 30
#     renewal:   10 points if renewing within 90 days AND has open critical cases
#   tiers: >= 80 Healthy, >= 60 Watch, otherwise At risk
UPTIME_WEIGHT, UPTIME_CAP = 10, 40
ROAMING_BASELINE, ROAMING_WEIGHT, ROAMING_CAP = 2, 5, 25
CASE_WEIGHT, CASE_CAP = 10, 30
RENEWAL_PENALTY = 10


def build_health_frame(customers, health, cases, subscriptions, lookback_days: int = 7):
    """Pure DataFrame logic, separated from table I/O so it can be unit-tested locally."""
    recent = health.filter(F.col("METRIC_DATE") >= F.dateadd("day", F.lit(-lookback_days), F.current_date()))
    device = recent.group_by("CUSTOMER_ID").agg(
        F.avg("UPTIME_PCT").alias("AVG_UPTIME_PCT_7D"),
        F.avg("ROAMING_FAILURE_COUNT").alias("AVG_DAILY_ROAMING_FAILURES_7D"),
    )
    critical = (
        cases.filter(F.col("IS_OPEN") & F.col("IS_CRITICAL"))
        .group_by("CUSTOMER_ID")
        .agg(F.count("CASE_ID").alias("OPEN_CRITICAL_CASES"))
    )
    renewals = subscriptions.group_by("CUSTOMER_ID").agg(
        F.max(F.iff(F.col("IS_RENEWING_WITHIN_90_DAYS"), F.lit(1), F.lit(0))).alias("RENEWING_90D"),
        F.sum(F.iff(F.col("IS_RENEWING_WITHIN_90_DAYS"), F.col("ANNUAL_VALUE_USD"), F.lit(0))).alias(
            "ANNUAL_VALUE_RENEWING_90D_USD"
        ),
    )

    df = (
        customers.select("CUSTOMER_ID", "CUSTOMER_NAME", "INDUSTRY", "PARTNER_ID")
        .join(device, "CUSTOMER_ID", "left")
        .join(critical, "CUSTOMER_ID", "left")
        .join(renewals, "CUSTOMER_ID", "left")
        .with_column("AVG_UPTIME_PCT_7D", F.coalesce(F.col("AVG_UPTIME_PCT_7D"), F.lit(100.0)))
        .with_column("AVG_DAILY_ROAMING_FAILURES_7D", F.coalesce(F.col("AVG_DAILY_ROAMING_FAILURES_7D"), F.lit(0.0)))
        .with_column("OPEN_CRITICAL_CASES", F.coalesce(F.col("OPEN_CRITICAL_CASES"), F.lit(0)))
        .with_column("RENEWING_90D", F.coalesce(F.col("RENEWING_90D"), F.lit(0)))
        .with_column("ANNUAL_VALUE_RENEWING_90D_USD", F.coalesce(F.col("ANNUAL_VALUE_RENEWING_90D_USD"), F.lit(0)))
    )

    uptime_pen = F.least((F.lit(100) - F.col("AVG_UPTIME_PCT_7D")) * UPTIME_WEIGHT, F.lit(UPTIME_CAP))
    roaming_pen = F.least(
        F.greatest(F.col("AVG_DAILY_ROAMING_FAILURES_7D") - ROAMING_BASELINE, F.lit(0)) * ROAMING_WEIGHT,
        F.lit(ROAMING_CAP),
    )
    case_pen = F.least(F.col("OPEN_CRITICAL_CASES") * CASE_WEIGHT, F.lit(CASE_CAP))
    renewal_pen = F.iff((F.col("RENEWING_90D") == 1) & (F.col("OPEN_CRITICAL_CASES") > 0),
                        F.lit(RENEWAL_PENALTY), F.lit(0))
    score = F.greatest(F.lit(0), F.lit(100) - uptime_pen - roaming_pen - case_pen - renewal_pen)

    return (
        df.with_column("HEALTH_SCORE", F.round(score, 1))
        .with_column(
            "RISK_TIER",
            F.when(F.col("HEALTH_SCORE") >= 80, F.lit("Healthy"))
            .when(F.col("HEALTH_SCORE") >= 60, F.lit("Watch"))
            .otherwise(F.lit("At risk")),
        )
        .with_column("COMPUTED_AT", F.current_timestamp())
    )


def compute_customer_health(session: Session) -> str:
    db = _current_database(session)
    marts = f"{db}.MARTS"
    scores = build_health_frame(
        session.table(f"{marts}.DIM_CUSTOMER"),
        session.table(f"{marts}.FCT_DEVICE_HEALTH_DAILY"),
        session.table(f"{marts}.FCT_SUPPORT_CASES"),
        session.table(f"{marts}.FCT_SUBSCRIPTIONS"),
    )

    current, history = f"{db}.OPS.CUSTOMER_HEALTH_SCORES", f"{db}.OPS.CUSTOMER_HEALTH_HISTORY"

    # Secure both tables with the same tenant policy as the marts (idempotent). The tables are
    # created once by deploy_ops.py setup and refilled here, so grants and the policy persist.
    for table in (current, history):
        session.sql(f"alter table {table} drop all row access policies").collect()
        session.sql(f"alter table {table} add row access policy {db}.SECURITY.TENANT_POLICY on (partner_id)").collect()

    scores.write.save_as_table(current, mode="truncate", column_order="name")
    scores_now = session.table(current)
    scores_now.write.save_as_table(history, mode="append", column_order="name")

    tiers = {r["RISK_TIER"]: r["N"] for r in scores_now.group_by("RISK_TIER").agg(F.count("*").alias("N")).collect()}
    return json.dumps({"table": current, "customers": sum(tiers.values()), "tiers": tiers})


# --------------------------------------------------------------------------
# 3. RUN_AGENT_EVAL: the Stage 5A eval, inside Snowflake, with every response stored
# --------------------------------------------------------------------------
def run_agent_eval(session: Session, agent_fqn: str) -> str:
    db = _current_database(session)
    run_id = str(uuid.uuid4())
    questions = agent_eval.load_questions()
    insert = f"""
        insert into {db}.OPS.AGENT_EVAL_RUNS
            (run_id, run_at, agent_name, question_id, question, expected_tools, tools_used,
             routing_ok, facts_ok, missing, answer, latency_ms, error, response)
        select ?, current_timestamp(), ?, ?, ?, parse_json(?), parse_json(?),
               ?, ?, parse_json(?), ?, ?, ?, parse_json(?)
    """
    passed = 0
    for q in questions:
        started = time.monotonic()
        try:
            response = agent_eval.run_agent(session, agent_fqn, q["question"])
            tools, answer = agent_eval.summarize(response)
            routing_ok, facts_ok, missing = agent_eval.score(q, tools, answer)
            error = None
        except Exception as exc:  # record the failure and keep going
            response, tools, answer, routing_ok, facts_ok, missing, error = {}, set(), "", False, False, [], str(exc)
        latency_ms = int((time.monotonic() - started) * 1000)
        passed += routing_ok and facts_ok
        session.sql(insert, params=[
            run_id, agent_fqn, q["id"], q["question"], json.dumps(q.get("expected_tools", [])),
            json.dumps(sorted(tools)), routing_ok, facts_ok, json.dumps(missing), answer, latency_ms,
            error, json.dumps(response),
        ]).collect()
    return json.dumps({"run_id": run_id, "agent": agent_fqn, "fully_correct": passed, "questions": len(questions)})
