"""Network-free tests for the private GitHub connector routes.

Every test drives the FastAPI app with ``TestClient`` and overrides
``require_user`` so no Supabase call is made.  The ``GitHubAppClient`` and the
connection store are replaced with in-memory fakes, so nothing here touches the
network or a database.
"""
import time

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("cryptography")

from fastapi.testclient import TestClient

from backend.app.auth import require_user
from backend.app.main import app
from backend.app.services import github_app, github_connection_store, token_crypto

client = TestClient(app)

_CONNECT_URL = "/api/v1/integrations/github/connect-url"
_CALLBACK = "/api/v1/integrations/github/callback"
_CONNECTIONS = "/api/v1/integrations/github/connections"

_CALLER = {"id": "user-1", "workspace_id": "ws-1"}
_PLAINTEXT_TOKEN = "gho_plaintext_secret_token"


class _FakeGitHubClient:
    """Stand-in for ``GitHubAppClient`` that never performs I/O."""

    oauth_base = "https://github.com"
    client_id = "test-client-id"
    callback_url = "https://app.example.com/api/v1/integrations/github/callback"

    def __init__(self, *args, **kwargs):
        pass

    @staticmethod
    def is_configured():
        return True

    @staticmethod
    def missing_env_vars():
        return []

    def exchange_user_code(self, code):
        return _PLAINTEXT_TOKEN

    def resolve_installation(self, installation_id):
        return {
            "id": int(installation_id),
            "account": {"login": "octo-org", "type": "Organization"},
            "permissions": {"contents": "read", "metadata": "read"},
        }

    def list_installations(self):
        return [{"id": 42, "account": {"login": "octo-org", "type": "Organization"}}]


@pytest.fixture
def configured(monkeypatch):
    """All GitHub App env vars plus a valid encryption key are present."""
    for name in github_app.GITHUB_ENV_VARS:
        monkeypatch.setenv(name, "test-value")
    monkeypatch.setenv(token_crypto.ENCRYPTION_KEY_ENV, token_crypto.generate_key())
    monkeypatch.setattr(github_app, "GitHubAppClient", _FakeGitHubClient)


@pytest.fixture
def authed():
    app.dependency_overrides[require_user] = lambda: dict(_CALLER)
    yield
    app.dependency_overrides.pop(require_user, None)


def test_connect_url_requires_authentication(monkeypatch):
    """Without a session the route fails closed with 401."""
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    res = client.get(_CONNECT_URL)
    assert res.status_code == 401, (res.status_code, res.text)


def test_connect_url_fails_closed_when_unconfigured(configured, authed, monkeypatch):
    """503 while the connector or the encryption key is unavailable."""
    for name in github_app.GITHUB_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv(token_crypto.ENCRYPTION_KEY_ENV, raising=False)
    res = client.get(_CONNECT_URL)
    assert res.status_code == 503, (res.status_code, res.text)


def test_connect_url_returns_a_signed_state(configured, authed):
    res = client.get(_CONNECT_URL)
    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body) == {"authorize_url", "state"}
    assert body["authorize_url"].startswith("https://github.com/login/oauth/authorize?")
    assert "client_id=test-client-id" in body["authorize_url"]
    assert "state=" in body["authorize_url"]
    verified = token_crypto.verify_state(body["state"])
    assert verified["user_id"] == _CALLER["id"]
    assert verified["workspace_id"] == _CALLER["workspace_id"]


def test_callback_rejects_a_tampered_state(configured, authed):
    state = token_crypto.sign_state(_CALLER["id"], _CALLER["workspace_id"])
    payload, signature = state.split(".", 1)
    tampered = f"{payload}.{'A' * len(signature)}"
    res = client.post(_CALLBACK, json={"code": "abc", "state": tampered, "installation_id": 42})
    assert res.status_code == 400, (res.status_code, res.text)


def test_callback_rejects_an_expired_state(configured, authed):
    expired = token_crypto.sign_state(
        _CALLER["id"],
        _CALLER["workspace_id"],
        now=int(time.time()) - token_crypto.STATE_TTL_SECONDS - 100,
    )
    res = client.post(_CALLBACK, json={"code": "abc", "state": expired, "installation_id": 42})
    assert res.status_code == 400, (res.status_code, res.text)


def test_callback_stores_an_encrypted_token(configured, authed, monkeypatch):
    captured: dict = {}

    def fake_upsert(**kwargs):
        captured.update(kwargs)
        return {
            "id": "11111111-1111-1111-1111-111111111111",
            "installation_id": kwargs["installation_id"],
            "account_login": kwargs["account_login"],
            "account_type": kwargs["account_type"],
            "token_expires_at": None,
            "scopes": kwargs["scopes"],
            "permissions": kwargs["permissions"],
            "created_at": None,
            "updated_at": None,
        }

    monkeypatch.setattr(github_connection_store, "upsert_connection", fake_upsert)

    state = token_crypto.sign_state(_CALLER["id"], _CALLER["workspace_id"])
    res = client.post(_CALLBACK, json={"code": "abc", "state": state, "installation_id": 42})
    assert res.status_code == 200, res.text

    body = res.json()
    assert body["installation_id"] == 42
    assert body["account_login"] == "octo-org"
    assert body["account_type"] == "Organization"

    # The stored credential is the encrypted envelope, never the plaintext.
    ciphertext = captured["token_ciphertext"]
    assert isinstance(ciphertext, bytes)
    assert ciphertext.startswith(b"KGC1")
    assert _PLAINTEXT_TOKEN.encode() not in ciphertext
    assert captured["token_key_version"] == token_crypto.current_key_version()
    assert token_crypto.decrypt_token(ciphertext) == _PLAINTEXT_TOKEN
    assert _PLAINTEXT_TOKEN not in {str(value) for value in captured.values()}

    # No token material is echoed back to the caller.
    assert _PLAINTEXT_TOKEN not in res.text
    assert "token_ciphertext" not in res.text
    assert "token" not in body


def test_list_connections_is_token_free(configured, authed, monkeypatch):
    monkeypatch.setattr(
        github_connection_store,
        "list_connections",
        lambda: [
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "installation_id": 42,
                "account_login": "octo-org",
                "account_type": "Organization",
                "token_expires_at": None,
                "scopes": None,
                "permissions": {"contents": "read"},
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        ],
    )
    res = client.get(_CONNECTIONS)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total"] == 1
    assert body["items"][0]["installation_id"] == 42
    assert "token_ciphertext" not in res.text
    assert "token" not in body["items"][0]


def test_disconnect_returns_not_found_for_an_unknown_id(configured, authed, monkeypatch):
    monkeypatch.setattr(github_connection_store, "delete_connection", lambda connection_id: 0)
    res = client.delete(f"{_CONNECTIONS}/22222222-2222-2222-2222-222222222222")
    assert res.status_code == 404, (res.status_code, res.text)


def test_disconnect_reports_the_deleted_row(configured, authed, monkeypatch):
    monkeypatch.setattr(github_connection_store, "delete_connection", lambda connection_id: 1)
    conn_id = "22222222-2222-2222-2222-222222222222"
    res = client.delete(f"{_CONNECTIONS}/{conn_id}")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body == {"ok": True, "connection_id": conn_id, "deleted": 1}
