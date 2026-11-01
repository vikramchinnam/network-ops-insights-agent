"""Offline tests for the agent client: no Snowflake connection needed."""

import json

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

import client


@pytest.fixture
def key_file(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    path = tmp_path / "key.p8"
    path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return path, key


def test_jwt_claims_follow_snowflake_format(key_file):
    path, key = key_file
    token = client.make_jwt("myorg-myacct", "vikram", str(path))
    claims = jwt.decode(token, key.public_key(), algorithms=["RS256"])
    assert claims["sub"] == "MYORG-MYACCT.VIKRAM"
    assert claims["iss"].startswith("MYORG-MYACCT.VIKRAM.SHA256:")
    assert 0 < claims["exp"] - claims["iat"] <= 3600


def test_jwt_strips_region_suffix_from_locator(key_file):
    path, _ = key_file
    token = client.make_jwt("xy12345.us-east-2.aws", "u", str(path))
    assert jwt.decode(token, options={"verify_signature": False})["sub"] == "XY12345.U"


def test_account_url_replaces_underscores():
    assert client.account_url("MYORG-MY_ACCT") == "https://myorg-my-acct.snowflakecomputing.com"


class FakeResponse:
    def __init__(self, lines):
        self._lines = lines

    def iter_lines(self, decode_unicode=True):
        yield from self._lines


def test_sse_parser_yields_events_in_order():
    lines = [
        "event: response.status", 'data: {"status": "planning"}', "",
        "event: response.text.delta", 'data: {"text": "Hello"}', "",
        "event: response.text.delta", 'data: {"text": " world"}', "",
        "event: some.future.event", 'data: {"x": 1}', "",
    ]
    events = list(client.iter_sse(FakeResponse(lines)))
    assert [e for e, _ in events] == [
        "response.status", "response.text.delta", "response.text.delta", "some.future.event"]
    assert "".join(d["text"] for e, d in events if e == "response.text.delta") == "Hello world"


def test_sse_parser_tolerates_non_json_data():
    events = list(client.iter_sse(FakeResponse(["event: x", "data: not json", ""])))
    assert events == [("x", {"raw": "not json"})]
