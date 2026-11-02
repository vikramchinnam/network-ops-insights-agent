"""Snowflake connections for the app.

Two kinds of connection:
  user_connection(user_token)  runs as the person asking. In SPCS this is caller's rights: the
                               login token is "<service token>.<Sf-Context-Current-User-Token>",
                               so row access policies and grants apply to that user's role.
  service_connection()         runs as the service itself (owner role NOI_SPCS). Used only to
                               write the request log, never to answer questions.
"""

from __future__ import annotations

import os
from contextlib import contextmanager

import snowflake.connector

from app.settings import SPCS_TOKEN_FILE, Settings


def _spcs_token() -> str:
    # Snowflake refreshes this file every few minutes; read it fresh for each connection
    return SPCS_TOKEN_FILE.read_text().strip()


def _connect(settings: Settings, user_token: str | None, as_service: bool):
    common = {"warehouse": settings.warehouse, "database": settings.database, "client_session_keep_alive": False}
    if settings.mode == "spcs":
        token = _spcs_token() if as_service or not user_token else f"{_spcs_token()}.{user_token}"
        return snowflake.connector.connect(
            host=os.environ["SNOWFLAKE_HOST"], account=os.environ["SNOWFLAKE_ACCOUNT"],
            authenticator="oauth", token=token, **common,
        )
    # local mode: key-pair as your user, acting as a single persona role
    conn = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"], user=os.environ["SNOWFLAKE_USER"],
        authenticator="SNOWFLAKE_JWT", private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
        role="NOI_DBT_DEV" if as_service else settings.local_role, **common,
    )
    if not as_service:
        # Only this persona's privileges, like a real single-role user (see Stage 5B)
        conn.cursor().execute("use secondary roles none")
    return conn


@contextmanager
def user_connection(settings: Settings, user_token: str | None):
    conn = _connect(settings, user_token, as_service=False)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def service_connection(settings: Settings):
    conn = _connect(settings, None, as_service=True)
    try:
        yield conn
    finally:
        conn.close()


def query(conn, sql: str, params: tuple | None = None) -> list[dict]:
    cur = conn.cursor(snowflake.connector.DictCursor)
    cur.execute(sql, params)
    return cur.fetchall()
