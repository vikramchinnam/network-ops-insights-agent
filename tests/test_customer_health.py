"""Customer health score logic, tested with Snowpark local testing (no Snowflake connection)."""

from datetime import date, timedelta

import pandas as pd
import pytest

snowpark = pytest.importorskip("snowflake.snowpark")
from snowflake.snowpark import Session  # noqa: E402
from snowflake.snowpark import functions as F  # noqa: E402
from snowflake.snowpark.mock import ColumnEmulator, ColumnType, patch  # noqa: E402
from snowflake.snowpark.types import DoubleType  # noqa: E402

from noi_snowpark.procedures import build_health_frame  # noqa: E402


@patch(F.round)  # local testing doesn't implement ROUND; emulate it with pandas
def _mock_round(e, scale=0):
    digits = int(scale.iloc[0]) if hasattr(scale, "iloc") else int(scale)
    result = ColumnEmulator(pd.to_numeric(e).round(digits))
    result.sf_type = ColumnType(DoubleType(), True)
    return result


@pytest.fixture(scope="module")
def scores():
    s = Session.builder.config("local_testing", True).create()
    today = date.today()
    customers = s.create_dataframe(
        [["C1", "Good Co", "Retail", "P1"], ["C2", "Bad Co", "Healthcare", "P1"], ["C3", "Quiet Co", "Hospitality", "P2"]],
        schema=["CUSTOMER_ID", "CUSTOMER_NAME", "INDUSTRY", "PARTNER_ID"])
    health = s.create_dataframe(
        [["C1", today - timedelta(days=1), 99.9, 1.0],
         ["C2", today - timedelta(days=1), 97.0, 8.0],
         ["C2", today - timedelta(days=30), 50.0, 50.0]],          # outside the 7-day window
        schema=["CUSTOMER_ID", "METRIC_DATE", "UPTIME_PCT", "ROAMING_FAILURE_COUNT"])
    cases = s.create_dataframe(
        [["K1", "C2", True, True], ["K2", "C2", True, True], ["K3", "C1", False, True]],
        schema=["CASE_ID", "CUSTOMER_ID", "IS_OPEN", "IS_CRITICAL"])
    subs = s.create_dataframe(
        [["C2", True, 1000.0], ["C1", False, 500.0]],
        schema=["CUSTOMER_ID", "IS_RENEWING_WITHIN_90_DAYS", "ANNUAL_VALUE_USD"])
    rows = build_health_frame(customers, health, cases, subs).collect()
    return {r["CUSTOMER_ID"]: r for r in rows}


def test_healthy_customer(scores):
    # uptime 99.9 -> -1; roaming 1 is under the baseline of 2; closed case doesn't count
    assert scores["C1"]["HEALTH_SCORE"] == 99
    assert scores["C1"]["RISK_TIER"] == "Healthy"


def test_at_risk_customer_applies_every_penalty_and_ignores_old_data(scores):
    # uptime 97 -> -30; roaming (8-2)*5=30 capped at 25; 2 critical cases -> -20; renewing + critical -> -10
    assert scores["C2"]["AVG_UPTIME_PCT_7D"] == 97.0
    assert scores["C2"]["HEALTH_SCORE"] == 15
    assert scores["C2"]["RISK_TIER"] == "At risk"


def test_customer_without_telemetry_defaults_to_full_health(scores):
    assert scores["C3"]["HEALTH_SCORE"] == 100
    assert scores["C3"]["OPEN_CRITICAL_CASES"] == 0
