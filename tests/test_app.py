"""Chat app tests with a fake Snowflake backend: no connection needed."""

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from app.main import USER_TOKEN_HEADER, create_app  # noqa: E402
from app.settings import Settings  # noqa: E402
from app.trace import build_trace, find_key  # noqa: E402

AGENT_RESPONSE = {
    "content": [
        {"type": "thinking", "thinking": {"text": "Need metrics, then the KB."}},
        {"type": "tool_use", "tool_use": {"name": "system_execute_sql", "type": "system_execute_sql",
                                          "input": {"sql": "select firmware_version from x"}}},
        {"type": "tool_result", "tool_result": {"name": "system_execute_sql", "status": "success",
                                                "content": [{"json": {"sql": "select firmware_version from x"}}]}},
        {"type": "tool_use", "tool_use": {"name": "KnowledgeBase", "type": "cortex_search",
                                          "input": {"query": "roaming fix 10.2.1"}}},
        {"type": "text", "text": "Upgrade to 10.3.0 (KB-1001)."},
    ],
    "metadata": {"usage": {"tokens": 1234}},
}


class FakeBackend:
    def __init__(self, role="NOI_SUPPORT", fail_obs=False):
        self.role, self.fail_obs, self.logged, self.tokens = role, fail_obs, [], []
        self.settings = Settings(mode="local", database="NOI_DEV", warehouse="NOI_WH_DEV",
                                 internal_agent="NOI_DEV.AGENTS.NETWORK_OPS_AGENT",
                                 partner_agent="NOI_DEV.AGENTS.NETWORK_OPS_PARTNER_AGENT",
                                 partner_roles=["NOI_PARTNER_PTR_001"])

    def whoami(self, token):
        self.tokens.append(token)
        return {"user": "VIKRAM", "role": self.role, "agent": self.settings.agent_for_role(self.role), "mode": "local"}

    def ask(self, token, question):
        self.tokens.append(token)
        return {"user": "VIKRAM", "role": self.role, "agent": self.settings.agent_for_role(self.role)}, AGENT_RESPONSE

    def log_request(self, record):
        self.logged.append(record)

    def observability(self, token):
        if self.fail_obs:
            raise PermissionError("no grants")
        return {"eval_runs": [], "cost_daily": [], "agent_daily": [], "recent_requests": []}

    def request_detail(self, token, request_id):
        return {"QUESTION": "q", "USER_NAME": "VIKRAM", "ROLE_NAME": self.role, "LATENCY_MS": 10,
                "RESPONSE": '{"content": [{"type": "text", "text": "hi"}]}'} if request_id == "known" else None


def client(backend):
    return TestClient(create_app(backend))


def test_health_and_index():
    c = client(FakeBackend())
    assert c.get("/healthz").json() == {"status": "ok"}
    assert "Network Ops Insights" in c.get("/").text


def test_chat_returns_answer_trace_and_logs_it():
    backend = FakeBackend()
    r = client(backend).post("/api/chat", json={"question": "Why roaming problems?"})
    body = r.json()
    assert r.status_code == 200
    assert body["answer"] == "Upgrade to 10.3.0 (KB-1001)."
    assert body["tools"] == ["KnowledgeBase", "NetworkMetrics"]
    assert any(s.get("sql") == "select firmware_version from x" for s in body["steps"])
    assert backend.logged[0]["question"] == "Why roaming problems?"


def test_caller_token_header_is_passed_through():
    backend = FakeBackend()
    client(backend).get("/api/whoami", headers={USER_TOKEN_HEADER: "user-token-123"})
    assert backend.tokens == ["user-token-123"]


def test_partner_role_gets_partner_agent():
    who = client(FakeBackend(role="NOI_PARTNER_PTR_001")).get("/api/whoami").json()
    assert who["agent"].endswith("NETWORK_OPS_PARTNER_AGENT")


def test_observability_denied_becomes_403():
    r = client(FakeBackend(fail_obs=True)).get("/api/observability")
    assert r.status_code == 403 and "internal roles" in r.json()["detail"]


def test_request_detail_found_and_missing():
    c = client(FakeBackend())
    assert c.get("/api/requests/known").json()["answer"] == "hi"
    assert c.get("/api/requests/nope").status_code == 404


def test_empty_question_rejected():
    assert client(FakeBackend()).post("/api/chat", json={"question": ""}).status_code == 422


def test_trace_helpers():
    trace = build_trace(AGENT_RESPONSE)
    assert [s["kind"] for s in trace["steps"]] == ["thinking", "tool_use", "tool_result", "tool_use"]
    assert trace["usage"] == {"tokens": 1234}
    assert find_key({"a": [{"b": {"sql": "x"}}]}, "sql") == "x"
