"""Score the Cortex Agent against the question set in snowpark/src/noi_snowpark/agent_questions.yaml.

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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import AGENTS, ENVIRONMENTS, agent_fqn  # noqa: E402

RESULTS_DIR = Path(__file__).with_name("results")

# Shared with the RUN_AGENT_EVAL stored procedure (Stage 6): one implementation in two places.
from noi_snowpark.agent_eval import load_questions, run_agent, score, summarize  # noqa: E402,F401


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", choices=list(ENVIRONMENTS), default="dev")
    parser.add_argument("--agent", choices=list(AGENTS), default="internal")
    parser.add_argument("--only", help="run a single question id")
    parser.add_argument("--show-answers", action="store_true")
    args = parser.parse_args()

    from noi_snowpark.generate_data import create_session

    questions = load_questions()
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
