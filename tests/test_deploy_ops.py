"""Offline tests for the OPS setup, grants and task SQL."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("deploy_ops", ROOT / "snowpark" / "deploy_ops.py")
deploy_ops = importlib.util.module_from_spec(spec)
sys.modules["deploy_ops"] = deploy_ops
spec.loader.exec_module(deploy_ops)


def test_setup_creates_schema_stage_and_tables():
    sql = "\n".join(deploy_ops.setup_sql("dev"))
    for obj in ("NOI_DEV.OPS", "SNOWPARK_ARTIFACTS", "AGENT_EVAL_RUNS", "CUSTOMER_HEALTH_SCORES", "CUSTOMER_HEALTH_HISTORY"):
        assert obj in sql


def test_partners_can_read_scores_but_not_eval_runs():
    sql = deploy_ops.grants_sql("dev")
    assert "grant select on table NOI_DEV.OPS.CUSTOMER_HEALTH_SCORES to role NOI_PARTNER_PTR_001" in sql
    assert not any("AGENT_EVAL_RUNS" in s and "NOI_PARTNER" in s for s in sql)
    assert "grant select on table NOI_DEV.OPS.AGENT_EVAL_RUNS to role NOI_SUPPORT" in sql


def test_tasks_are_created_suspended_unless_resumed():
    assert not any("resume" in s for s in deploy_ops.tasks_sql("dev", resume=False))
    assert sum("resume" in s for s in deploy_ops.tasks_sql("dev", resume=True)) == 2
    assert "call NOI_DEV.OPS.RUN_AGENT_EVAL('NOI_DEV.AGENTS.NETWORK_OPS_AGENT')" in deploy_ops.tasks_sql("dev", False)[1]
