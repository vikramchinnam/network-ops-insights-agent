"""Turn a Cortex Agent response into a readable trace for the UI.

A DATA_AGENT_RUN response has a `content` list of items: thinking, tool_use, tool_result, text.
Since April 2026 the metrics step appears as a `system_execute_sql` tool whose result carries
the final SQL. This module flattens that into ordered steps the trace panel can render.
"""

from __future__ import annotations

from typing import Any

SQL_TOOL_TYPES = {"system_execute_sql", "cortex_analyst_text_to_sql"}
MAX_TEXT = 4000


def find_key(obj: Any, key: str) -> Any:
    """Depth-first search for the first value stored under `key` in nested dicts/lists."""
    if isinstance(obj, dict):
        if key in obj and obj[key]:
            return obj[key]
        for value in obj.values():
            found = find_key(value, key)
            if found:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = find_key(value, key)
            if found:
                return found
    return None


def _clip(text: Any, limit: int = MAX_TEXT) -> str:
    text = text if isinstance(text, str) else str(text)
    return text if len(text) <= limit else text[:limit] + " …"


def build_trace(response: dict) -> dict:
    steps, answer, tools = [], [], set()
    for item in response.get("content", []):
        kind = item.get("type")
        if kind == "thinking":
            steps.append({"kind": "thinking", "text": _clip(find_key(item, "text") or "")})
        elif kind == "tool_use":
            use = item.get("tool_use", {})
            name, tool_type = use.get("name", ""), use.get("type", "")
            label = "NetworkMetrics" if tool_type in SQL_TOOL_TYPES or name in SQL_TOOL_TYPES else name
            tools.add(label)
            steps.append({"kind": "tool_use", "tool": label, "type": tool_type,
                          "sql": find_key(use, "sql"), "query": find_key(use, "query"),
                          "input": _clip(use.get("input", ""))})
        elif kind == "tool_result":
            result = item.get("tool_result", {})
            steps.append({"kind": "tool_result", "tool": result.get("name") or result.get("type", ""),
                          "status": result.get("status"), "sql": find_key(result, "sql"),
                          "content": _clip(result.get("content", ""))})
        elif kind == "text":
            answer.append(item.get("text", ""))
    usage = find_key(response.get("metadata", {}), "usage")
    return {"answer": "\n".join(answer).strip(), "tools": sorted(tools), "steps": steps, "usage": usage}
