"""Deploy Cortex Agents from their version-controlled specs.

Usage (from the repo root):
    uv run python agent/deploy_agent.py --env dev                    # all agents
    uv run python agent/deploy_agent.py --env dev --agent partner    # one agent
    uv run python agent/deploy_agent.py --env dev --dry-run          # print the SQL only

Each agent's spec lives in agent/<spec>.yaml (see config.AGENTS). This script fills in the
environment's database and warehouse, validates the YAML, runs CREATE OR REPLACE AGENT, and
grants USAGE to the roles allowed to use that agent. CREATE OR REPLACE drops existing grants,
so they are reapplied on every deploy. The same script runs in CI (Stage 8).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from string import Template

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from config import AGENT_SCHEMA, AGENTS, ENVIRONMENTS, agent_fqn  # noqa: E402

AGENT_DIR = Path(__file__).parent


def render_spec(env: str, agent: str = "internal") -> str:
    cfg = ENVIRONMENTS[env]
    spec = Template((AGENT_DIR / AGENTS[agent]["spec"]).read_text(encoding="utf-8")).substitute(
        DATABASE=cfg["database"], WAREHOUSE=cfg["warehouse"]
    )
    parsed = yaml.safe_load(spec)  # fail fast on YAML mistakes, before Snowflake sees them
    tool_names = {t["tool_spec"]["name"] for t in parsed["tools"]}
    missing = tool_names - set(parsed.get("tool_resources", {}))
    if missing:
        raise ValueError(f"{agent}: tools without tool_resources: {sorted(missing)}")
    if "$$" in spec:
        raise ValueError(f"{agent}: spec must not contain $$ (it is the SQL string delimiter)")
    return spec


def build_sql(env: str, agent: str = "internal") -> list[str]:
    db = ENVIRONMENTS[env]["database"]
    fqn = agent_fqn(env, agent)
    statements = [
        f"create schema if not exists {db}.{AGENT_SCHEMA}",
        f"create or replace agent {fqn}\n"
        f"  comment = 'Network Ops Insights {agent} agent (deployed from agent/{AGENTS[agent]['spec']})'\n"
        f"  from specification\n$$\n{render_spec(env, agent)}$$",
    ]
    for role in AGENTS[agent]["grant_to"]:
        statements.append(f"grant usage on schema {db}.{AGENT_SCHEMA} to role {role}")
        statements.append(f"grant usage on agent {fqn} to role {role}")
    return statements


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy Cortex Agents.")
    parser.add_argument("--env", choices=list(ENVIRONMENTS), default="dev")
    parser.add_argument("--agent", choices=["all", *AGENTS], default="all")
    parser.add_argument("--dry-run", action="store_true", help="print the SQL without running it")
    args = parser.parse_args()

    agents = list(AGENTS) if args.agent == "all" else [args.agent]
    if args.dry_run:
        for agent in agents:
            print(";\n\n".join(build_sql(args.env, agent)) + ";\n")
        return

    from noi_snowpark.generate_data import create_session  # same key-pair session as the generator

    session = create_session(args.env)
    try:
        for agent in agents:
            for sql in build_sql(args.env, agent):
                session.sql(sql).collect()
            print(f"Deployed {agent_fqn(args.env, agent)}  (usage granted to {', '.join(AGENTS[agent]['grant_to'])})")
    finally:
        session.close()


if __name__ == "__main__":
    main()
