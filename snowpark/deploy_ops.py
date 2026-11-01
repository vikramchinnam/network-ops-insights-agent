"""Set up the OPS schema around the Snowpark procedures, and schedule them.

Usage (from the repo root):
    uv run python snowpark/deploy_ops.py setup  --env dev   # before dbt build and `snow snowpark deploy`
    uv run python snowpark/deploy_ops.py grants --env dev   # read access for the persona roles
    uv run python snowpark/deploy_ops.py tasks  --env dev   # create (suspended) tasks
    uv run python snowpark/deploy_ops.py tasks  --env dev --resume   # turn the schedules on

setup   creates the OPS schema, the artifact stage and the tables the procedures write to.
grants  lets internal and partner roles read health scores (the tenant policy filters rows) and
        internal roles read eval runs.
tasks   creates two Snowflake Tasks that call the procedures on a schedule. They are created
        SUSPENDED so nothing runs (or costs) until you choose to resume them.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
from config import AGENTS, ENVIRONMENTS, agent_fqn  # noqa: E402

TIMEZONE = "America/Chicago"


def setup_sql(env: str) -> list[str]:
    db = ENVIRONMENTS[env]["database"]
    return [
        f"create schema if not exists {db}.OPS",
        f"create stage if not exists {db}.OPS.SNOWPARK_ARTIFACTS comment = 'Snowpark procedure code (snow snowpark deploy)'",
        f"""create table if not exists {db}.OPS.AGENT_EVAL_RUNS (
                run_id          varchar     comment 'One id per eval run (all questions)',
                run_at          timestamp_ltz,
                agent_name      varchar     comment 'Fully qualified agent evaluated',
                question_id     varchar,
                question        varchar,
                expected_tools  array,
                tools_used      array,
                routing_ok      boolean,
                facts_ok        boolean,
                missing         array,
                answer          varchar,
                latency_ms      number,
                error           varchar,
                response        variant     comment 'Full DATA_AGENT_RUN response: tool calls, SQL, search hits (the trace)'
            ) comment = 'One row per question per agent eval run, written by RUN_AGENT_EVAL'""",
        *[f"""create table if not exists {db}.OPS.{name} (
                customer_id                    varchar,
                customer_name                  varchar,
                industry                       varchar,
                partner_id                     varchar,
                avg_uptime_pct_7d              float,
                avg_daily_roaming_failures_7d  float,
                open_critical_cases            number,
                renewing_90d                   number,
                annual_value_renewing_90d_usd  float,
                health_score                   float,
                risk_tier                      varchar,
                computed_at                    timestamp_ltz
            ) comment = '{comment}'""" for name, comment in (
            ("CUSTOMER_HEALTH_SCORES", "Latest health score per customer (COMPUTE_CUSTOMER_HEALTH)"),
            ("CUSTOMER_HEALTH_HISTORY", "Every health score computed, for trends (COMPUTE_CUSTOMER_HEALTH)"),
        )],
    ]


def grants_sql(env: str) -> list[str]:
    db = ENVIRONMENTS[env]["database"]
    internal, partners = AGENTS["internal"]["grant_to"], AGENTS["partner"]["grant_to"]
    statements = []
    for role in internal + partners:
        statements += [
            f"grant usage on schema {db}.OPS to role {role}",
            f"grant select on table {db}.OPS.CUSTOMER_HEALTH_SCORES to role {role}",   # rows filtered by TENANT_POLICY
        ]
    for role in internal:
        statements += [
            f"grant select on table {db}.OPS.CUSTOMER_HEALTH_HISTORY to role {role}",
            f"grant select on table {db}.OPS.AGENT_EVAL_RUNS to role {role}",
        ]
    return statements


def tasks_sql(env: str, resume: bool) -> list[str]:
    cfg = ENVIRONMENTS[env]
    db, wh = cfg["database"], cfg["warehouse"]
    statements = [
        f"""create or replace task {db}.OPS.TASK_CUSTOMER_HEALTH
                warehouse = {wh}
                schedule = 'USING CRON 0 6 * * * {TIMEZONE}'
                comment = 'Daily customer health scores'
            as call {db}.OPS.COMPUTE_CUSTOMER_HEALTH()""",
        f"""create or replace task {db}.OPS.TASK_AGENT_EVAL
                warehouse = {wh}
                schedule = 'USING CRON 0 7 * * 1 {TIMEZONE}'
                comment = 'Weekly agent evaluation (Mondays)'
            as call {db}.OPS.RUN_AGENT_EVAL('{agent_fqn(env, "internal")}')""",
    ]
    if resume:
        statements += [f"alter task {db}.OPS.TASK_CUSTOMER_HEALTH resume", f"alter task {db}.OPS.TASK_AGENT_EVAL resume"]
    return statements


def main() -> None:
    parser = argparse.ArgumentParser(description="OPS schema setup and task scheduling.")
    parser.add_argument("action", choices=["setup", "grants", "tasks"])
    parser.add_argument("--env", choices=list(ENVIRONMENTS), default="dev")
    parser.add_argument("--resume", action="store_true", help="tasks: resume schedules after creating them")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    statements = {"setup": lambda: setup_sql(args.env), "grants": lambda: grants_sql(args.env),
                  "tasks": lambda: tasks_sql(args.env, args.resume)}[args.action]()
    if args.dry_run:
        print(";\n\n".join(statements) + ";")
        return

    from noi_snowpark.generate_data import create_session

    session = create_session(args.env)
    try:
        for sql in statements:
            session.sql(sql).collect()
    finally:
        session.close()
    state = "resumed" if args.resume else "created suspended"
    print(f"{args.action}: done for {ENVIRONMENTS[args.env]['database']}.OPS" + (f" (tasks {state})" if args.action == "tasks" else ""))


if __name__ == "__main__":
    main()
