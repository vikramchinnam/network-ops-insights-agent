"""Deploy and operate the chat app on Snowpark Container Services.

Usage (from the repo root), after pushing the image:
    uv run python spcs/deploy_service.py deploy --env dev --tag v1   # create or update the service
    uv run python spcs/deploy_service.py status --env dev            # container status
    uv run python spcs/deploy_service.py logs   --env dev            # last 100 log lines
    uv run python spcs/deploy_service.py url    --env dev            # the public endpoint URL
    uv run python spcs/deploy_service.py deploy --env dev --tag v1 --dry-run

Runs as NOI_SPCS, the role that owns the service. The service spec template is
spcs/service_spec.yaml; CREATE (first time) or ALTER ... FROM SPECIFICATION (updates).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from string import Template

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
from config import AGENTS, ENVIRONMENTS  # noqa: E402

SPEC_FILE = Path(__file__).with_name("service_spec.yaml")
SERVICE_ROLE = "NOI_SPCS"
POOLS = {"dev": "NOI_POOL", "prod": "NOI_POOL_PROD"}
IMAGE_NAME = "noi_app"


def service_fqn(env: str) -> str:
    return f"{ENVIRONMENTS[env]['database']}.SPCS.NOI_APP"


def image_path(env: str, tag: str) -> str:
    # Image paths inside a spec are lowercase: /<database>/<schema>/<repository>/<image>:<tag>
    return f"/{ENVIRONMENTS[env]['database'].lower()}/spcs/images/{IMAGE_NAME}:{tag}"


def render_spec(env: str, tag: str) -> str:
    cfg = ENVIRONMENTS[env]
    spec = Template(SPEC_FILE.read_text(encoding="utf-8")).substitute(
        IMAGE=image_path(env, tag), DATABASE=cfg["database"], WAREHOUSE=cfg["warehouse"])
    parsed = yaml.safe_load(spec)  # fail fast on YAML mistakes
    assert parsed["capabilities"]["securityContext"]["executeAsCaller"] is True
    if "$$" in spec:
        raise ValueError("spec must not contain $$")
    return spec


def deploy_sql(env: str, tag: str, exists: bool) -> list[str]:
    fqn, spec = service_fqn(env), render_spec(env, tag)
    if exists:
        statements = [f"alter service {fqn} from specification\n$$\n{spec}$$"]
    else:
        statements = [
            f"create service {fqn}\n  in compute pool {POOLS[env]}\n  from specification\n$$\n{spec}$$\n"
            f"  query_warehouse = {ENVIRONMENTS[env]['warehouse']}\n  min_instances = 1\n  max_instances = 1\n"
            f"  comment = 'Network Ops Insights chat app'"
        ]
    # Who may open the endpoint: internal support and partner roles
    for role in AGENTS["internal"]["grant_to"] + AGENTS["partner"]["grant_to"]:
        statements.append(f"grant service role {fqn}!ALL_ENDPOINTS_USAGE to role {role}")
    return statements


def main() -> None:
    parser = argparse.ArgumentParser(description="Operate the chat app service.")
    parser.add_argument("action", choices=["deploy", "status", "logs", "url"])
    parser.add_argument("--env", choices=list(ENVIRONMENTS), default="dev")
    parser.add_argument("--tag", default="v1", help="image tag to deploy")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    fqn = service_fqn(args.env)

    if args.dry_run:
        print(";\n\n".join(deploy_sql(args.env, args.tag, exists=False)) + ";")
        return

    from noi_snowpark.generate_data import create_session

    session = create_session(args.env, role=SERVICE_ROLE)
    try:
        if args.action == "deploy":
            db = ENVIRONMENTS[args.env]["database"]
            exists = bool(session.sql(f"show services like 'NOI_APP' in schema {db}.SPCS").collect())
            for sql in deploy_sql(args.env, args.tag, exists):
                session.sql(sql).collect()
            print(f"{'Updated' if exists else 'Created'} {fqn} with image tag {args.tag}. "
                  f"It takes a few minutes to start; check with: status")
        elif args.action == "status":
            raw = session.sql(f"select system$get_service_status('{fqn}') as s").collect()[0]["S"]
            for c in json.loads(raw):
                print(f"{c.get('containerName')}: {c.get('status')}  {c.get('message', '')}  image={c.get('image', '')}")
        elif args.action == "logs":
            print(session.sql(f"select system$get_service_logs('{fqn}', 0, 'app', 100) as l").collect()[0]["L"])
        elif args.action == "url":
            rows = session.sql(f"show endpoints in service {fqn}").collect()
            for r in rows:
                d = r.as_dict()
                print(f"{d.get('name')}: https://{d.get('ingress_url')}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
