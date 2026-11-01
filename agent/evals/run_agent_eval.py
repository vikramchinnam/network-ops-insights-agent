"""Score the Cortex Agent against agent/evals/agent_questions.yaml.

Usage (from the repo root):
    uv run python agent/evals/run_agent_eval.py
    uv run python agent/evals/run_agent_eval.py --only a03_why_and_what_to_do --show-answers

Runs each question through SNOWFLAKE.CORTEX.DATA_AGENT_RUN in a SQL session (non-streaming),
reads which tools the agent used, and checks routing and required facts. Running through SQL
means the agent runs as the session's role, which Stage 5B uses to test different personas.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import AGENTS, ENVIRONMENTS, agent_fqn  # noqa: E402

EVAL_FILE = Path(__file__).with_name("agent_questions.yaml")
RESULTS_DIR = Path(__file__).with_name("results")

# Since April 2026, agents generate SQL from semantic views themselves; that step appears as a
# tool of type "system_execute_sql" rather than the Analyst tool's own name. Count it as NetworkMetrics.
SQL_TOOL_TYPES = {"system_execute_sql", "cortex_analyst_text_to_sql"}


def run_agent(session, agent: str, question: str) -> dict:
    body = {"messages": [{"role": "user", "content": [{"type": "text", "text": question}]}]}
    row = session.sql(
        "select snowflake.cortex.data_agent_run(?, ?) as r", params=[agent, json.dumps(body)]
    ).collect()[0]
    return json.loads(row["R"])


def summarize(response: dict) -> tuple[set[str], str]:
    """Return (tools used, answer text) from a DATA_AGENT_RUN response."""
    tools, texts = set(), []
    for item in response.get("content", []):
        kind = item.get("type")
        if kind == "tool_use":
            use = item.get("tool_use", {})
            name, tool_type = use.get("name", ""), use.get("type", "")
            tools.add("NetworkMetrics" if tool_type in SQL_TOOL_TYPES or name in SQL_TOOL_TYPES else name)
        elif kind == "text":
            texts.append(item.get("text", ""))
    return tools, "\n".join(texts).strip()


def score(q: dict, tools: set[str], answer: str) -> tuple[bool, bool, list[str]]:
    expected = set(q.get("expected_tools", []))
    routing_ok = (not tools) if not expected else expected <= tools
    # Each must_mention entry is a phrase, or a list of acceptable alternatives (any one counts),
    # e.g. ["2026-12-31", "December 31, 2026"] so the check doesn't fail on date formatting.
    text = answer.lower()
    missing = []
    for item in q.get("must_mention", []):
        options = item if isinstance(item, list) else [item]
        if not any(opt.lower() in text for opt in options):
            missing.append(item)
    return routing_ok, not missing, missing


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", choices=list(ENVIRONMENTS), default="dev")
    parser.add_argument("--agent", choices=list(AGENTS), default="internal")
    parser.add_argument("--only", help="run a single question id")
    parser.add_argument("--show-answers", action="store_true")
    args = parser.parse_args()

    from noi_snowpark.generate_data import create_session

    questions = yaml.safe_load(EVAL_FILE.read_text())["questions"]
    if args.only:
        questions = [q for q in questions if q["id"] == args.only]

    agent = agent_fqn(args.env, args.agent)
    session = create_session(args.env)
    results = []
    print(f"\nAgent: {agent}   role: {session.get_current_role()}\n")
    print(f"{'ID':<26} {'ROUTING':<8} {'FACTS':<6} TOOLS USED")
    try:
        for q in questions:
            try:
                tools, answer = summarize(run_agent(session, agent, q["question"]))
                routing_ok, facts_ok, missing = score(q, tools, answer)
                error = None
            except Exception as exc:  # keep going; one failure shouldn't hide the rest
                tools, answer, routing_ok, facts_ok, missing, error = set(), "", False, False, [], str(exc)
            note = f"  missing: {missing}" if missing else (f"  ERROR: {error[:80]}" if error else "")
            print(f"{q['id']:<26} {'pass' if routing_ok else 'FAIL':<8} {'pass' if facts_ok else 'FAIL':<6} "
                  f"{', '.join(sorted(tools)) or '(none)'}{note}")
            if args.show_answers and answer:
                print("    " + answer.replace("\n", "\n    ")[:1500] + "\n")
            results.append({"id": q["id"], "tools": sorted(tools), "routing_ok": routing_ok,
                            "facts_ok": facts_ok, "missing": missing, "error": error, "answer": answer})
    finally:
        session.close()

    n = len(results)
    routing = sum(r["routing_ok"] for r in results)
    facts = sum(r["facts_ok"] for r in results)
    both = sum(r["routing_ok"] and r["facts_ok"] for r in results)
    print(f"\nrouting: {routing}/{n}   facts: {facts}/{n}   fully correct: {both}/{n}\n")

    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"agent_eval_{args.env}_{datetime.now():%Y%m%d_%H%M}.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"Saved details to {out}")


if __name__ == "__main__":
    main()
