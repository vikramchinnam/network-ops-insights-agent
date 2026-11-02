"""Network Ops Insights chat app.

    GET  /                       the web UI (chat + trace panel, observability page)
    GET  /healthz                readiness probe for Snowpark Container Services
    GET  /api/whoami             who you are, your role, which agent you'll talk to
    POST /api/chat               ask the agent; returns the answer and a step-by-step trace
    GET  /api/observability      cost, eval and request data (internal roles only)
    GET  /api/requests/{id}      full trace of an earlier request

Run locally:   uv run uvicorn app.main:app --app-dir spcs --port 8080
In SPCS, Snowflake adds the Sf-Context-Current-User-Token header to every request (because the
service spec sets executeAsCaller: true); the app uses it to act as the signed-in user.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.settings import Settings, load_settings
from app.trace import build_trace

STATIC_DIR = Path(__file__).parent / "static"
USER_TOKEN_HEADER = "Sf-Context-Current-User-Token"


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class Backend:
    """Everything that touches Snowflake. Tests replace this with a fake."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def whoami(self, user_token: str | None) -> dict:
        from app.snowflake_access import query, user_connection

        with user_connection(self.settings, user_token) as conn:
            row = query(conn, "select current_user() as user_name, current_role() as role_name")[0]
        role = row["ROLE_NAME"]
        return {"user": row["USER_NAME"], "role": role, "agent": self.settings.agent_for_role(role),
                "mode": self.settings.mode}

    def ask(self, user_token: str | None, question: str) -> tuple[dict, dict]:
        from app.snowflake_access import query, user_connection

        with user_connection(self.settings, user_token) as conn:
            who = query(conn, "select current_user() as user_name, current_role() as role_name")[0]
            agent = self.settings.agent_for_role(who["ROLE_NAME"])
            body = json.dumps({"messages": [{"role": "user", "content": [{"type": "text", "text": question}]}]})
            row = query(conn, "select snowflake.cortex.data_agent_run(%s, %s) as r", (agent, body))[0]
        identity = {"user": who["USER_NAME"], "role": who["ROLE_NAME"], "agent": agent}
        return identity, json.loads(row["R"])

    def log_request(self, record: dict) -> None:
        from app.snowflake_access import service_connection

        with service_connection(self.settings) as conn:
            conn.cursor().execute(
                f"""insert into {self.settings.database}.OPS.APP_REQUESTS
                      (request_id, requested_at, user_name, role_name, agent_name, question, answer,
                       tools_used, latency_ms, error, response)
                    select %s, current_timestamp(), %s, %s, %s, %s, %s, parse_json(%s), %s, %s, parse_json(%s)""",
                (record["request_id"], record["user"], record["role"], record["agent"], record["question"],
                 record["answer"], json.dumps(record["tools"]), record["latency_ms"], record["error"],
                 json.dumps(record["response"])),
            )

    def observability(self, user_token: str | None) -> dict:
        from app.snowflake_access import query, user_connection

        db = self.settings.database
        sql = {
            "eval_runs": f"""select run_id, run_at, agent_name, questions, fully_correct, fully_correct_rate,
                                    avg_latency_s from {db}.OBSERVABILITY.FCT_EVAL_RUNS
                             order by run_at desc limit 10""",
            "cost_daily": f"""select usage_date, cost_category, round(sum(credits), 4) as credits
                              from {db}.OBSERVABILITY.FCT_AI_COST_DAILY
                              where usage_date >= dateadd(day, -14, current_date())
                              group by 1, 2 order by 1, 2""",
            "agent_daily": f"""select date(start_time) as day, count(*) as requests,
                                      round(sum(credits), 4) as credits,
                                      round(sum(credits) / nullif(count(*), 0), 5) as credits_per_request,
                                      round(avg(duration_s), 1) as avg_duration_s
                               from {db}.OBSERVABILITY.FCT_AGENT_REQUESTS
                               where start_time >= dateadd(day, -14, current_timestamp())
                               group by 1 order by 1 desc""",
            "recent_requests": f"""select request_id, requested_at, user_name, role_name, agent_name, question,
                                          latency_ms, error, tools_used
                                   from {db}.OPS.APP_REQUESTS order by requested_at desc limit 20""",
        }
        with user_connection(self.settings, user_token) as conn:
            return {name: query(conn, statement) for name, statement in sql.items()}

    def request_detail(self, user_token: str | None, request_id: str) -> dict | None:
        from app.snowflake_access import query, user_connection

        with user_connection(self.settings, user_token) as conn:
            rows = query(conn, f"select * from {self.settings.database}.OPS.APP_REQUESTS where request_id = %s",
                         (request_id,))
        return rows[0] if rows else None


def create_app(backend: Backend | None = None) -> FastAPI:
    app = FastAPI(title="Network Ops Insights", docs_url=None, redoc_url=None)
    app.state.backend = backend or Backend(load_settings())

    def get_backend() -> Backend:
        return app.state.backend

    def user_token(request: Request) -> str | None:
        return request.headers.get(USER_TOKEN_HEADER)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/whoami")
    def whoami(token: str | None = Depends(user_token), backend: Backend = Depends(get_backend)):
        try:
            return backend.whoami(token)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Could not connect to Snowflake: {exc}") from exc

    @app.post("/api/chat")
    def chat(req: ChatRequest, token: str | None = Depends(user_token), backend: Backend = Depends(get_backend)):
        request_id, started = str(uuid.uuid4()), time.monotonic()
        identity, response, error = {"user": None, "role": None, "agent": None}, {}, None
        try:
            identity, response = backend.ask(token, req.question)
        except Exception as exc:
            error = str(exc)
        latency_ms = int((time.monotonic() - started) * 1000)
        trace = build_trace(response)
        try:  # logging must never break the answer
            backend.log_request({"request_id": request_id, **identity, "question": req.question,
                                 "answer": trace["answer"], "tools": trace["tools"], "latency_ms": latency_ms,
                                 "error": error, "response": response})
        except Exception:
            pass
        if error:
            raise HTTPException(status_code=502, detail=f"The agent could not answer: {error}")
        return {"request_id": request_id, "latency_ms": latency_ms, **identity, **trace}

    @app.get("/api/observability")
    def observability(token: str | None = Depends(user_token), backend: Backend = Depends(get_backend)):
        try:
            return backend.observability(token)
        except Exception as exc:
            # Partner roles have no grants on these views: that's the access model working
            raise HTTPException(status_code=403,
                                detail="Observability is available to internal roles only.") from exc

    @app.get("/api/requests/{request_id}")
    def request_detail(request_id: str, token: str | None = Depends(user_token),
                       backend: Backend = Depends(get_backend)):
        try:
            row = backend.request_detail(token, request_id)
        except Exception as exc:
            raise HTTPException(status_code=403, detail="Request history is available to internal roles only.") from exc
        if not row:
            raise HTTPException(status_code=404, detail="Request not found.")
        response = row.get("RESPONSE")
        response = json.loads(response) if isinstance(response, str) else (response or {})
        return {"request_id": request_id, "question": row.get("QUESTION"), "user": row.get("USER_NAME"),
                "role": row.get("ROLE_NAME"), "latency_ms": row.get("LATENCY_MS"), **build_trace(response)}

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


app = create_app()
