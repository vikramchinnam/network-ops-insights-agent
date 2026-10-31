"""Score Cortex Search against agent/evals/search_queries.yaml.

Usage (from the repo root):
    uv run python agent/evals/run_search_eval.py                 # search all documents
    uv run python agent/evals/run_search_eval.py --docs-only     # exclude support cases
    uv run python agent/evals/run_search_eval.py --env prod

Metrics:
    hit@5  share of queries where an expected document is in the top 5
    MRR    mean reciprocal rank of the first expected document (1/rank, 0 if missing)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from noi_snowpark.generate_data import ENVIRONMENTS, create_session

EVAL_FILE = Path(__file__).with_name("search_queries.yaml")
TOP_K = 5


def search(session, service: str, query: str, docs_only: bool) -> list[dict]:
    request = {"query": query, "columns": ["doc_id", "doc_type", "title"], "limit": TOP_K}
    if docs_only:
        request["filter"] = {"@not": {"@eq": {"doc_type": "support_case"}}}
    row = session.sql(
        "select snowflake.cortex.search_preview(?, ?) as r", params=[service, json.dumps(request)]
    ).collect()[0]
    return json.loads(row["R"])["results"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", choices=list(ENVIRONMENTS), default="dev")
    parser.add_argument("--docs-only", action="store_true", help="exclude support cases from results")
    args = parser.parse_args()

    service = f"{ENVIRONMENTS[args.env]['database']}.SEARCH.SUPPORT_DOCS"
    queries = yaml.safe_load(EVAL_FILE.read_text())["queries"]
    session = create_session(args.env)

    hits, reciprocal_ranks = 0, []
    print(f"\nService: {service}   docs-only: {args.docs_only}\n")
    print(f"{'ID':<24} {'HIT':<5} {'RANK':<5} TOP RESULT")
    try:
        for q in queries:
            results = search(session, service, q["query"], args.docs_only)
            ids = [r["doc_id"] for r in results]
            rank = next((i + 1 for i, doc in enumerate(ids) if doc in q["expected"]), None)
            hits += rank is not None
            reciprocal_ranks.append(1 / rank if rank else 0.0)
            top = f"{results[0]['doc_id']}  {results[0]['title'][:50]}" if results else "(no results)"
            print(f"{q['id']:<24} {'yes' if rank else 'NO':<5} {rank or '-':<5} {top}")
    finally:
        session.close()

    n = len(queries)
    print(f"\nhit@{TOP_K}: {hits}/{n} = {hits / n:.0%}     MRR: {sum(reciprocal_ranks) / n:.2f}\n")


if __name__ == "__main__":
    main()
