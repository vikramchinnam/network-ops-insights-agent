"""Offline tests for agent eval scoring."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "run_agent_eval", Path(__file__).resolve().parents[1] / "agent" / "evals" / "run_agent_eval.py")
run_agent_eval = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_agent_eval)


def test_summarize_maps_sql_tool_to_network_metrics():
    response = {"content": [
        {"type": "tool_use", "tool_use": {"name": "system_execute_sql", "type": "system_execute_sql"}},
        {"type": "tool_use", "tool_use": {"name": "KnowledgeBase", "type": "cortex_search"}},
        {"type": "text", "text": "Upgrade to 10.3.0 (KB-1001)."},
    ]}
    tools, answer = run_agent_eval.summarize(response)
    assert tools == {"NetworkMetrics", "KnowledgeBase"}
    assert "10.3.0" in answer


def test_score_routing_and_facts():
    q = {"expected_tools": ["KnowledgeBase"], "must_mention": ["10.3.0", "KB-1001"]}
    assert run_agent_eval.score(q, {"KnowledgeBase"}, "see kb-1001, upgrade to 10.3.0") == (True, True, [])
    assert run_agent_eval.score(q, {"CaseHistory"}, "nothing") == (False, False, ["10.3.0", "KB-1001"])


def test_score_out_of_scope_requires_no_tools():
    q = {"expected_tools": [], "must_mention": []}
    assert run_agent_eval.score(q, set(), "I can't help with that.")[0] is True
    assert run_agent_eval.score(q, {"KnowledgeBase"}, "...")[0] is False

def test_score_accepts_alternatives():
    q = {"expected_tools": [], "must_mention": ["AX-400", ["2026-12-31", "December 31, 2026"]]}
    assert run_agent_eval.score(q, set(), "Replace with the AX-400 before December 31, 2026.")[2] == []
    missing = run_agent_eval.score(q, set(), "Replace with the AX-400.")[2]
    assert missing == [["2026-12-31", "December 31, 2026"]]