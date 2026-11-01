"""Offline tests for the tenant leakage checks."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("run_tenant_eval", ROOT / "agent" / "evals" / "run_tenant_eval.py")
run_tenant_eval = importlib.util.module_from_spec(spec)
sys.modules["run_tenant_eval"] = run_tenant_eval  # dataclasses need the module registered
spec.loader.exec_module(run_tenant_eval)

DIRECTORY = [
    {"CUSTOMER_NAME": "Riverside Health System", "PARTNER_ID": "PTR-001", "PARTNER_NAME": "Smith Networks"},
    {"CUSTOMER_NAME": "Lakeview Unified School District", "PARTNER_ID": "PTR-002", "PARTNER_NAME": "Jones IT Services"},
    {"CUSTOMER_NAME": "Hilltop Hotels & Resorts", "PARTNER_ID": "PTR-003", "PARTNER_NAME": "Lee Solutions"},
]


def test_forbidden_names_exclude_own_partner():
    forbidden = run_tenant_eval.forbidden_names_for({"PTR-001"}, DIRECTORY)
    assert "Riverside Health System" not in forbidden and "Smith Networks" not in forbidden
    assert {"Lakeview Unified School District", "Jones IT Services", "Hilltop Hotels & Resorts"} <= forbidden


def test_find_leaks_is_case_insensitive():
    forbidden = run_tenant_eval.forbidden_names_for({"PTR-001"}, DIRECTORY)
    assert run_tenant_eval.find_leaks("Your customer Riverside Health System renews soon.", forbidden) == []
    assert run_tenant_eval.find_leaks("lakeview unified school district has 3 cases", forbidden) == [
        "Lakeview Unified School District"]


def test_personas_come_from_the_seed():
    personas = run_tenant_eval.load_personas()
    roles = {p.role: p for p in personas}
    assert roles["NOI_SUPPORT"].allowed is None and roles["NOI_SUPPORT"].agent == "internal"
    assert roles["NOI_PARTNER_PTR_001"].allowed == {"PTR-001"}
    assert roles["NOI_PARTNER_PTR_001"].agent == "partner"


def test_probes_include_an_injection_attempt():
    assert any("ignore your previous instructions" in q.lower() for q in run_tenant_eval.PROBES)
