"""Agent evaluation logic shared by the local runner and the Snowpark procedure.

One implementation, two places it runs:
  - agent/evals/run_agent_eval.py        on your laptop (Stage 5A)
  - procedures.run_agent_eval            inside Snowflake, scheduled by a Task (Stage 6)

The question set lives in this package (agent_questions.yaml) so it ships with the procedure.
"""

from __future__ import annotations

import json
from importlib import resources

import yaml

# Since April 2026, agents generate SQL from semantic views themselves; that step appears as a
# tool of type "system_execute_sql" rather than the Analyst tool's own name. Count it as NetworkMetrics.
SQL_TOOL_TYPES = {"system_execute_sql", "cortex_analyst_text_to_sql"}


def load_questions() -> list[dict]:
    # importlib.resources works both from a folder and from the zip Snowflake imports
    text = resources.files("noi_snowpark").joinpath("agent_questions.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(text)["questions"]


def run_agent(session, agent: str, question: str) -> dict:
    """Run one question through SNOWFLAKE.CORTEX.DATA_AGENT_RUN as the session's role."""
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


def score(q: dict, tools: set[str], answer: str) -> tuple[bool, bool, list]:
    """(routing_ok, facts_ok, missing). An empty expected_tools list means 'use no tools'.
    Each must_mention entry is a phrase, or a list of alternatives (any one counts)."""
    expected = set(q.get("expected_tools", []))
    routing_ok = (not tools) if not expected else expected <= tools
    text = answer.lower()
    missing = []
    for item in q.get("must_mention", []):
        options = item if isinstance(item, list) else [item]
        if not any(opt.lower() in text for opt in options):
            missing.append(item)
    return routing_ok, not missing, missing
