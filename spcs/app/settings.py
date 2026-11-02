"""Runtime settings from environment variables. One image, two modes:

  spcs   running on Snowpark Container Services: Snowflake provides /snowflake/session/token,
         SNOWFLAKE_HOST and SNOWFLAKE_ACCOUNT. Queries run as the signed-in user (caller's rights).
  local  running on your laptop or in `docker run`: key-pair login from SNOWFLAKE_ACCOUNT,
         SNOWFLAKE_USER and SNOWFLAKE_PRIVATE_KEY_PATH, acting as NOI_LOCAL_ROLE (a persona).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

SPCS_TOKEN_FILE = Path("/snowflake/session/token")


def _list(value: str) -> list[str]:
    return [v.strip().upper() for v in value.split(",") if v.strip()]


@dataclass(frozen=True)
class Settings:
    mode: str
    database: str
    warehouse: str
    internal_agent: str
    partner_agent: str
    partner_roles: list[str] = field(default_factory=list)
    local_role: str = "NOI_SUPPORT"

    def agent_for_role(self, role: str) -> str:
        """Partners get the partner agent; everyone else gets the internal agent."""
        return self.partner_agent if role.upper().strip('"') in self.partner_roles else self.internal_agent


def load_settings() -> Settings:
    database = os.getenv("NOI_DATABASE", "NOI_DEV")
    return Settings(
        mode="spcs" if SPCS_TOKEN_FILE.exists() else "local",
        database=database,
        warehouse=os.getenv("NOI_WAREHOUSE", "NOI_WH_DEV"),
        internal_agent=os.getenv("NOI_INTERNAL_AGENT", f"{database}.AGENTS.NETWORK_OPS_AGENT"),
        partner_agent=os.getenv("NOI_PARTNER_AGENT", f"{database}.AGENTS.NETWORK_OPS_PARTNER_AGENT"),
        partner_roles=_list(os.getenv("NOI_PARTNER_ROLES", "NOI_PARTNER_PTR_001,NOI_PARTNER_PTR_002")),
        local_role=os.getenv("NOI_LOCAL_ROLE", "NOI_SUPPORT").upper(),
    )
