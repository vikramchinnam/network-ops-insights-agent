"""Deploy the Cortex Agent from its version-controlled spec.

Usage (from the repo root):
    uv run python agent/deploy_agent.py --env dev
    uv run python agent/deploy_agent.py --env dev --dry-run   # print the SQL only

The spec lives in agent/network_ops_agent.yaml. This script fills in the environment's
database and warehouse, validates the YAML, and runs CREATE OR REPLACE AGENT. The same
script runs in CI (Stage 8), so Dev and Prod agents come from the same file.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from string import Template

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from config import AGENT_NAME, AGENT_SCHEMA, ENVIRONMENTS, agent_fqn  # noqa: E402

SPEC_FILE = Path(__file__).with_name("network_ops_agent.yaml")


def render_spec(env: str) -> str:
    cfg = ENVIRONMENTS[env]
    spec = Template(SPEC_FILE.read_text(encoding="utf-8")).substitute(
        DATABASE=cfg["database"], WAREHOUSE=cfg["warehouse"]
    )
    parsed = yaml.safe_load(spec)  # fail fast on YAML mistakes, before Snowflake sees them
    tool_names = {t["tool_spec"]["name"] for t in parsed["tools"]}
    missing = tool_names - set(parsed.get("tool_resources", {}))
    if missing:
        raise ValueError(f"tools without tool_resources: {sorted(missing)}")
    if "$$" in spec:
        raise ValueError("spec must not contain $$ (it is the SQL string delimiter)")
    return spec


def build_sql(env: str) -> list[str]:
    db = ENVIRONMENTS[env]["database"]
    return [
        f"create schema if not exists {db}.{AGENT_SCHEMA}",
        f"create or replace agent {agent_fqn(env)}\n"
        f"  comment = 'Network Ops Insights agent (deployed from agent/network_ops_agent.yaml)'\n"
        f"  from specification\n$$\n{render_spec(env)}$$",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy the Cortex Agent.")
    parser.add_argument("--env", choices=list(ENVIRONMENTS), default="dev")
    parser.add_argument("--dry-run", action="store_true", help="print the SQL without running it")
    args = parser.parse_args()

    statements = build_sql(args.env)
    if args.dry_run:
        print(";\n\n".join(statements) + ";")
        return

    from noi_snowpark.generate_data import create_session  # same key-pair session as the generator

    session = create_session(args.env)
    try:
        for sql in statements:
            session.sql(sql).collect()
        print(f"Deployed {agent_fqn(args.env)}")
        for row in session.sql(f"describe agent {agent_fqn(args.env)}").collect():
            d = row.as_dict()
            print(f"  name={d.get('name', AGENT_NAME)} owner={d.get('owner', '?')} schema={AGENT_SCHEMA}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
