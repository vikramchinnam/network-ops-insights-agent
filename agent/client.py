"""Talk to the Cortex Agent over the REST API, with the answer streamed as it is written.

Usage (from the repo root):
    uv run python agent/client.py "Which firmware has the most roaming failures?"
    uv run python agent/client.py --env dev            # interactive: type questions, Ctrl+C to quit
    uv run python agent/client.py --agent partner "Which of my customers renew soon?"

The REST call runs as your user's DEFAULT role. To try the partner agent as a partner, set your
default role to a partner role first; run_tenant_eval.py tests personas without changing it.

How it works:
  1. Sign a short-lived JWT with your private key (key-pair auth, no password).
  2. POST the question to  /api/v2/databases/{db}/schemas/AGENTS/agents/<agent>:run
  3. Read Server-Sent Events: print answer tokens as they arrive, and show which tools ran.

This is the same call the chat app's backend makes in Stage 7.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Iterator

import jwt
import requests
from cryptography.hazmat.primitives import serialization

sys.path.insert(0, str(Path(__file__).parent))
from config import AGENT_SCHEMA, AGENTS, ENVIRONMENTS, snowflake_credentials  # noqa: E402


# --------------------------------------------------------------------------
# Authentication: key-pair JWT
# --------------------------------------------------------------------------
def make_jwt(account: str, user: str, private_key_path: str, lifetime_s: int = 3600) -> str:
    """Build the JWT Snowflake expects for key-pair auth (valid for at most 1 hour)."""
    key = serialization.load_pem_private_key(Path(private_key_path).read_bytes(), password=None)
    public_der = key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    fingerprint = "SHA256:" + base64.b64encode(hashlib.sha256(public_der).digest()).decode()

    # Account part of the JWT: uppercase, without any region suffix (e.g. ORG-ACCT, or XY12345)
    acct = account.upper().split(".")[0]
    qualified_user = f"{acct}.{user.upper()}"
    now = int(time.time())
    payload = {"iss": f"{qualified_user}.{fingerprint}", "sub": qualified_user, "iat": now, "exp": now + lifetime_s}
    return jwt.encode(payload, key, algorithm="RS256")


def account_url(account: str) -> str:
    # Hostnames can't contain underscores, so ORG-MY_ACCT becomes org-my-acct
    return f"https://{account.lower().replace('_', '-')}.snowflakecomputing.com"


# --------------------------------------------------------------------------
# Server-Sent Events
# --------------------------------------------------------------------------
def iter_sse(response: requests.Response) -> Iterator[tuple[str, dict]]:
    """Yield (event_name, data) pairs from a text/event-stream response."""
    event, data_lines = "message", []
    for raw in response.iter_lines(decode_unicode=True):
        if raw is None:
            continue
        line = raw.rstrip("\r")
        if line == "":  # blank line = end of one event
            if data_lines:
                payload = "\n".join(data_lines)
                try:
                    yield event, json.loads(payload)
                except json.JSONDecodeError:
                    yield event, {"raw": payload}
            event, data_lines = "message", []
        elif line.startswith("event:"):
            event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:"):].strip())


# --------------------------------------------------------------------------
# Agent call
# --------------------------------------------------------------------------
def ask(question: str, env: str = "dev", show_tools: bool = True, agent: str = "internal") -> str:
    """Send one question, stream the answer to stdout, and return the full answer text."""
    creds = snowflake_credentials()
    db = ENVIRONMENTS[env]["database"]
    name = AGENTS[agent]["name"]
    url = f"{account_url(creds['account'])}/api/v2/databases/{db}/schemas/{AGENT_SCHEMA}/agents/{name}:run"
    headers = {
        "Authorization": f"Bearer {make_jwt(creds['account'], creds['user'], creds['private_key_path'])}",
        "X-Snowflake-Authorization-Token-Type": "KEYPAIR_JWT",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    body = {"messages": [{"role": "user", "content": [{"type": "text", "text": question}]}]}

    answer: list[str] = []
    with requests.post(url, headers=headers, json=body, stream=True, timeout=(10, 900)) as resp:
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        for event, data in iter_sse(resp):
            if event == "response.text.delta":
                text = data.get("text", "")
                answer.append(text)
                print(text, end="", flush=True)
            elif event == "response.tool_use" and show_tools:
                print(f"\n  [tool] {data.get('name') or data.get('type')}", file=sys.stderr, flush=True)
            elif event == "response.status" and show_tools:
                print(f"  [status] {data.get('message') or data.get('status')}", file=sys.stderr, flush=True)
            elif event == "error":
                raise RuntimeError(f"Agent error {data.get('code')}: {data.get('message')}")
            # Other events (thinking, tables, charts, metadata) are ignored here; the API
            # documentation says clients must tolerate event types they don't recognize.
    print()
    return "".join(answer)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask the Network Ops Insights agent a question.")
    parser.add_argument("question", nargs="?", help="omit for interactive mode")
    parser.add_argument("--env", choices=list(ENVIRONMENTS), default="dev")
    parser.add_argument("--quiet", action="store_true", help="hide tool and status lines")
    parser.add_argument("--agent", choices=list(AGENTS), default="internal")
    args = parser.parse_args()

    if args.question:
        ask(args.question, args.env, show_tools=not args.quiet, agent=args.agent)
        return

    print("Ask a question (Ctrl+C to quit).")
    try:
        while True:
            question = input("\nyou> ").strip()
            if question:
                print("agent> ", end="")
                ask(question, args.env, show_tools=not args.quiet, agent=args.agent)
    except (KeyboardInterrupt, EOFError):
        print()


if __name__ == "__main__":
    main()
