"""Shared settings for the agent scripts: one place for names that differ by environment or audience."""

from __future__ import annotations

import os

ENVIRONMENTS = {
    "dev": {"database": "NOI_DEV", "warehouse": "NOI_WH_DEV", "role": "NOI_DBT_DEV"},
    "prod": {"database": "NOI_PROD", "warehouse": "NOI_WH_PROD", "role": "NOI_DBT_PROD"},
}

AGENT_SCHEMA = "AGENTS"

# One agent per audience. grant_to: roles that receive USAGE on the agent at deploy time.
AGENTS = {
    "internal": {
        "name": "NETWORK_OPS_AGENT",
        "spec": "network_ops_agent.yaml",
        "grant_to": ["NOI_SUPPORT"],
    },
    "partner": {
        "name": "NETWORK_OPS_PARTNER_AGENT",
        "spec": "network_ops_partner_agent.yaml",
        "grant_to": ["NOI_PARTNER_PTR_001", "NOI_PARTNER_PTR_002"],
    },
}

# Kept for backwards compatibility with Stage 5A scripts
AGENT_NAME = AGENTS["internal"]["name"]


def agent_fqn(env: str, agent: str = "internal") -> str:
    """Fully qualified agent name, e.g. NOI_DEV.AGENTS.NETWORK_OPS_AGENT."""
    return f"{ENVIRONMENTS[env]['database']}.{AGENT_SCHEMA}.{AGENTS[agent]['name']}"


def snowflake_credentials() -> dict[str, str]:
    """Connection details from environment variables (the same ones dbt uses)."""
    return {
        "account": os.environ["SNOWFLAKE_ACCOUNT"],
        "user": os.environ["SNOWFLAKE_USER"],
        "private_key_path": os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
    }
