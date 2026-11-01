"""Shared settings for the agent scripts: one place for names that differ by environment."""

from __future__ import annotations

import os

ENVIRONMENTS = {
    "dev": {"database": "NOI_DEV", "warehouse": "NOI_WH_DEV", "role": "NOI_DBT_DEV"},
    "prod": {"database": "NOI_PROD", "warehouse": "NOI_WH_PROD", "role": "NOI_DBT_PROD"},
}

AGENT_SCHEMA = "AGENTS"
AGENT_NAME = "NETWORK_OPS_AGENT"


def agent_fqn(env: str) -> str:
    """Fully qualified agent name, e.g. NOI_DEV.AGENTS.NETWORK_OPS_AGENT."""
    return f"{ENVIRONMENTS[env]['database']}.{AGENT_SCHEMA}.{AGENT_NAME}"


def snowflake_credentials() -> dict[str, str]:
    """Connection details from environment variables (the same ones dbt uses)."""
    return {
        "account": os.environ["SNOWFLAKE_ACCOUNT"],
        "user": os.environ["SNOWFLAKE_USER"],
        "private_key_path": os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
    }
