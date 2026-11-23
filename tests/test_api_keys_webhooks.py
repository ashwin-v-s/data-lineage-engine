"""Offline contract tests for workspace API keys and webhooks (migration 0016).

No database and no network: connections answer scripted rows, delivery is
stubbed at the single ``webhook_delivery._post`` seam, and key authentication is
exercised through the real ``require_user`` dependency with the DB lookup
patched, so the read-only scope and path guards are covered end to end.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from psycopg2.extras import Json

from backend.app import db as dbmod
from backend.app.api.routes import api_keys as ak
from backend.app.api.routes import membership as m
from backend.app.api.routes import webhooks as w
from backend.app.auth import require_user
from backend.app.main import app
from backend.app.services import webhook_delivery as wd

USER = {"id": "user-1", "email": "tester@example.com"}
WORKSPACE = "11111111-1111-4111-8111-111111111111"
KEY_TOKEN = "kairos_sk_abc123def456_" + "x" * 20
KEY_HASH = hashlib.sha256(KEY_TOKEN.encode("utf-8")).hexdigest()
HOOK = "22222222-2222-4222-8222-222222222222"
MISSING_HOOK = "33333333-3333-4333-8333-333333333333"


class _Cursor:
    def __init__(self, conn):
        self.conn = conn
        self.stmts: list[tuple[str, tuple | None]] = []
        self._rows: list[tuple] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, sql, params=None):
        self.stmts.append((" ".join(sql.split()), params))
        for needle, fn in self.conn.handlers:
            if needle in sql:
                self._rows = fn(self.stmts, params) or []
                return
        raise AssertionError(f"Unexpected SQL in api key/webhook test: {sql[:160]}")

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class _Conn:
    def __init__(self, *handlers):
        self.handlers = list(handlers)
        self.cursor_obj: _Cursor | None = None

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def cursor(self, *args, **kwargs):
        self.cursor_obj = _Cursor(self)
        return self.cursor_obj

    def commit(self):
        pass

    def rollback(self):
        pass


def _regclass(table: str | None):
    return ("to_regclass", lambda stmts, params: [(table,)])


def _role(role: str):
    return ("SELECT role", lambda stmts, params: [(role,)])


def _rows(*rows):
    return ("id::text", lambda stmts, params: list(rows))


def _no_rows(needle: str):
    # Handler for DML whose RETURNING clause yields nothing.
    return (needle, lambda stmts, params: [])


@pytest.fixture
def workspace_scope():
    token = dbmod.set_workspace_id(WORKSPACE)
    try:
        yield
    finally:
        dbmod.reset_workspace_id(token)


@pytest.fixture
def client(workspace_scope):
    app.dependency_overrides[require_user] = lambda: USER
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(require_user, None)


@pytest.fixture
def key_client(workspace_scope):
    """No require_user override: real API-key authentication runs."""
    return TestClient(app)


def _use(monkeypatch, module, conn):
    monkeypatch.setattr(module, "get_conn", lambda: conn)
    return conn


def _use_all(monkeypatch, conn, *modules):
    for module in modules:
        monkeypatch.setattr(module, "get_conn", lambda: conn)
    return conn


# ── API keys: provisioning and role gate ─────────────────────────────────────


def test_api_keys_unprovisioned_returns_503(client, monkeypatch):
    conn = _Conn(_regclass(None), _role("owner"))
    _use_all(monkeypatch, conn, ak, m)
    response = client.get("/api/v1/api-keys")
    assert response.status_code == 503
    assert "0016" in response.text


def test_viewer_cannot_create_api_key(client, monkeypatch):
    conn = _Conn(_regclass("workspace_api_key"), _role("viewer"))
    _use_all(monkeypatch, conn, ak, m)
    response = client.post("/api/v1/api-keys", json={"name": "ci"})
    assert response.status_code == 403


def test_create_api_key_returns_secret_once_and_stores_only_hash(client, monkeypatch):
    created = ("key-1", "ci-key", "kairos_sk_abc123de", ["read"], datetime.now(timezone.utc), None, None)

    def insert(stmts, params):
        return [created]

    conn = _Conn(
        _regclass("workspace_api_key"),
        _role("admin"),
        ("SELECT id::text, revoked_at", lambda stmts, params: []),
        ("INSERT INTO workspace_api_key", insert),
    )
    _use_all(monkeypatch, conn, ak, m)
    response = client.post("/api/v1/api-keys", json={"name": "ci-key"})
    assert response.status_code == 201
    body = response.json()
    assert body["token"].startswith("kairos_sk_")
    assert body["key"]["prefix"] == "kairos_sk_abc123de"
    assert body["key"]["scopes"] == ["read"]
    # The persisted value is the SHA-256 of the returned token, never the token.
    sql, params = next((s, p) for s, p in conn.cursor_obj.stmts if "INSERT INTO workspace_api_key" in s)
    assert params[2] == hashlib.sha256(body["token"].encode()).hexdigest()
    assert body["token"] not in [str(value) for value in params]


def test_duplicate_active_key_name_conflicts(client, monkeypatch):
    active = ("key-1", None)
    conn = _Conn(
        _regclass("workspace_api_key"),
        _role("owner"),
        ("SELECT id::text, revoked_at", lambda stmts, params: [active]),
    )
    _use_all(monkeypatch, conn, ak, m)
    response = client.post("/api/v1/api-keys", json={"name": "ci-key"})
    assert response.status_code == 409
    assert not any("INSERT INTO workspace_api_key" in sql for sql, _ in conn.cursor_obj.stmts)


def test_revoked_key_name_can_be_replaced_without_reviving_old_secret(client, monkeypatch):
    revoked = ("key-1", datetime.now(timezone.utc))

    def update(stmts, params):
        return [("key-1", "ci-key", "kairos_sk_newprefix", ["read"],
                 datetime.now(timezone.utc), None, None)]

    conn = _Conn(
        _regclass("workspace_api_key"),
        _role("owner"),
        ("SELECT id::text, revoked_at", lambda stmts, params: [revoked]),
        ("UPDATE workspace_api_key", update),
    )
    _use_all(monkeypatch, conn, ak, m)
    response = client.post("/api/v1/api-keys", json={"name": "ci-key"})
    assert response.status_code == 201
    body = response.json()
    assert body["token"].startswith("kairos_sk_")
    assert body["key"]["revoked_at"] is None
    sql, params = next((s, p) for s, p in conn.cursor_obj.stmts if "UPDATE workspace_api_key" in s)
    assert params[1] == hashlib.sha256(body["token"].encode()).hexdigest()
    assert params[3] == "key-1"


def test_list_api_keys_never_returns_a_secret(client, monkeypatch):
    row = ("key-1", "ci-key", "kairos_sk_abc123de", ["read"], datetime.now(timezone.utc), None, None)
    conn = _Conn(_regclass("workspace_api_key"), _rows(row))
    _use(monkeypatch, ak, conn)
    response = client.get("/api/v1/api-keys")
    assert response.status_code == 200
    body = response.json()
    assert body["keys"][0]["prefix"] == "kairos_sk_abc123de"
    assert "token" not in body
    assert "secret_hash" not in str(body)


def test_revoke_unknown_key_returns_404(client, monkeypatch):
    conn = _Conn(_regclass("workspace_api_key"), _role("owner"), _no_rows("UPDATE workspace_api_key"))
    _use_all(monkeypatch, conn, ak, m)
    response = client.delete("/api/v1/api-keys/11111111-1111-4111-8111-222222222222")
    assert response.status_code == 404


def test_revoke_key_marks_it_revoked(client, monkeypatch):
    revoked = ("11111111-1111-4111-8111-222222222222",)
    conn = _Conn(
        _regclass("workspace_api_key"),
        _role("owner"),
        ("UPDATE workspace_api_key", lambda stmts, params: [revoked]),
    )
    _use_all(monkeypatch, conn, ak, m)
    response = client.delete("/api/v1/api-keys/11111111-1111-4111-8111-222222222222")
    assert response.status_code == 200
    assert response.json()["revoked"] is True


# ── API keys: authentication through require_user ────────────────────────────


def _patch_key_lookup(monkeypatch, record):
    monkeypatch.setattr(dbmod, "authenticate_api_key", lambda secret_hash: record)
    monkeypatch.setattr(dbmod, "_get_pool", lambda: pytest.fail("key auth must not open a route connection"))


def test_api_key_authenticates_self_lookup(key_client, monkeypatch, workspace_scope):
    _patch_key_lookup(
        monkeypatch,
        {"key_id": "key-1", "workspace_id": WORKSPACE, "name": "ci-key", "scopes": ["read"], "last_used_at": None},
    )
    row = ("key-1", "ci-key", "kairos_sk_abc123de", ["read"], datetime.now(timezone.utc), datetime.now(timezone.utc), None)
    conn = _Conn(_regclass("workspace_api_key"), _rows(row))
    _use(monkeypatch, ak, conn)
    response = key_client.get("/api/v1/api-keys/self", headers={"Authorization": f"Bearer {KEY_TOKEN}"})
    assert response.status_code == 200
    body = response.json()
    assert body["auth"] == "api_key"
    assert body["key"]["name"] == "ci-key"


def test_api_key_is_read_only(key_client, monkeypatch, workspace_scope):
    _patch_key_lookup(
        monkeypatch,
        {"key_id": "key-1", "workspace_id": WORKSPACE, "name": "ci", "scopes": ["read"], "last_used_at": None},
    )
    response = key_client.post(
        "/api/v1/webhooks",
        json={"url": "https://example.com/hook", "events": ["test.ping"]},
        headers={"Authorization": f"Bearer {KEY_TOKEN}"},
    )
    assert response.status_code == 403
    assert "read-only" in response.text.lower()


def test_api_key_read_surface_covers_catalog_and_assets_only():
    from backend.app.services.api_keys import path_allowed

    for path in (
        "/api/v1/catalog",
        "/api/v1/catalog/",
        "/api/v1/assets/6f1c1f30-0000-4000-8000-000000000000",
        "/api/v1/lineage/abc/upstream",
        "/api/v1/search",
        "/api/v1/health",
        "/api/v1/api-keys/self",
    ):
        assert path_allowed(path), path
    for path in ("/api/v1/members", "/api/v1/assets-malicious", "/api/v1/catalogx", "/health"):
        assert not path_allowed(path), path


def test_api_key_cannot_reach_unlisted_endpoints(key_client, monkeypatch, workspace_scope):
    _patch_key_lookup(
        monkeypatch,
        {"key_id": "key-1", "workspace_id": WORKSPACE, "name": "ci", "scopes": ["read"], "last_used_at": None},
    )
    response = key_client.get("/api/v1/members", headers={"Authorization": f"Bearer {KEY_TOKEN}"})
    assert response.status_code == 403
    assert "cannot access" in response.text.lower()


def test_revoked_or_unknown_key_returns_401(key_client, monkeypatch, workspace_scope):
    _patch_key_lookup(monkeypatch, None)
    response = key_client.get("/api/v1/api-keys/self", headers={"Authorization": f"Bearer {KEY_TOKEN}"})
    assert response.status_code == 401


def test_key_auth_failure_is_not_a_500(key_client, monkeypatch, workspace_scope):
    def boom(secret_hash):
        raise RuntimeError("pool exhausted")

    monkeypatch.setattr(dbmod, "authenticate_api_key", boom)
    response = key_client.get("/api/v1/api-keys/self", headers={"Authorization": f"Bearer {KEY_TOKEN}"})
    assert response.status_code == 503


# ── Webhooks: validation, storage and delivery ───────────────────────────────


def test_webhook_requires_https(client, monkeypatch):
    conn = _Conn(_regclass("workspace_webhook"), _role("owner"))
    _use_all(monkeypatch, conn, w, m)
    response = client.post("/api/v1/webhooks", json={"url": "http://insecure.example/x", "events": ["test.ping"]})
    assert response.status_code in (400, 422)
    assert not any("INSERT INTO workspace_webhook" in sql for sql, _ in conn.cursor_obj.stmts)


def test_webhook_rejects_unknown_event(client, monkeypatch):
    conn = _Conn(_regclass("workspace_webhook"), _role("owner"))
    _use_all(monkeypatch, conn, w, m)
    response = client.post(
        "/api/v1/webhooks",
        json={"url": "https://example.com/hook", "events": ["not.a.real.event"]},
    )
    assert response.status_code in (400, 422)


def test_webhook_rejects_private_literal_host(client, monkeypatch):
    conn = _Conn(_regclass("workspace_webhook"), _role("owner"))
    _use_all(monkeypatch, conn, w, m)
    for url in ("https://127.0.0.1/hook", "https://169.254.169.254/latest/meta-data", "https://localhost/hook"):
        response = client.post("/api/v1/webhooks", json={"url": url, "events": ["test.ping"]})
        assert response.status_code in (400, 422), url
        assert not any("INSERT INTO workspace_webhook" in sql for sql, _ in conn.cursor_obj.stmts)


def test_webhook_requires_encryption_key(client, monkeypatch):
    monkeypatch.setattr(w, "is_configured", lambda: False)
    conn = _Conn(_regclass("workspace_webhook"), _role("owner"))
    _use_all(monkeypatch, conn, w, m)
    response = client.post("/api/v1/webhooks", json={"url": "https://example.com/hook", "events": ["test.ping"]})
    assert response.status_code == 503
    assert "KAIROS_TOKEN_ENCRYPTION_KEY" in response.text


def test_create_webhook_stores_ciphertext_and_returns_secret_once(client, monkeypatch):
    monkeypatch.setattr(w, "is_configured", lambda: True)
    monkeypatch.setattr(w, "encrypt_token", lambda value: b"ENVELOPE:" + value.encode())

    def insert(stmts, params):
        assert params[3] == ["test.ping", "freshness.breach"]
        assert params[4].startswith(b"ENVELOPE:whsec_")
        return [(HOOK, "https://example.com/hook", "CI hook", ["test.ping", "freshness.breach"],
                 True, datetime.now(timezone.utc), None, None, None)]

    conn = _Conn(_regclass("workspace_webhook"), _role("admin"), ("INSERT INTO workspace_webhook", insert))
    _use_all(monkeypatch, conn, w, m)
    response = client.post(
        "/api/v1/webhooks",
        json={"url": "https://example.com/hook", "description": "CI hook",
              "events": ["test.ping", "freshness.breach"]},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["signing_secret"].startswith("whsec_")
    assert "ENVELOPE" not in str(body)


def test_delivery_refuses_private_destination(monkeypatch):
    import socket

    monkeypatch.setattr(
        wd.socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 443))],
    )

    def no_request(*args, **kwargs):
        raise AssertionError("delivery must not open a client for an internal destination")

    monkeypatch.setattr(wd.httpx, "Client", no_request)
    outcome = wd.deliver(
        {"id": HOOK, "url": "https://internal.example/hook", "workspace_id": WORKSPACE},
        "test.ping",
    )
    assert outcome["ok"] is False
    assert outcome["response_status"] is None
    assert "private or loopback" in (outcome["error"] or "")


def test_delivery_allows_public_destination(monkeypatch):
    import socket

    monkeypatch.setattr(
        wd.socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
    )
    seen: dict[str, str] = {}

    class _Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def post(self, url, content=None, headers=None):
            seen["url"] = url
            return type("R", (), {"status_code": 204, "text": ""})()

    monkeypatch.setattr(wd.httpx, "Client", _Client)
    outcome = wd.deliver(
        {"id": HOOK, "url": "https://example.com/hook", "workspace_id": WORKSPACE},
        "test.ping",
    )
    assert outcome["ok"] is True
    assert seen["url"] == "https://example.com/hook"


def test_test_delivery_records_success(client, monkeypatch):
    monkeypatch.setattr(
        wd, "_post",
        lambda url, body, headers: type("R", (), {"status_code": 200, "text": "ok"})(),
    )
    hook_row = (HOOK, "https://example.com/hook", WORKSPACE, b"cipher", True)

    def insert_delivery(stmts, params):
        # (webhook_id, event_type, payload, status, excerpt, ok, error, duration)
        assert params[0] == HOOK
        assert params[1] == "test.ping"
        assert isinstance(params[2], Json)
        assert params[3] == 200
        assert params[4] == "ok"
        assert params[5] is True
        assert params[6] is None
        return [("delivery-1", datetime.now(timezone.utc))]

    conn = _Conn(
        _regclass("workspace_webhook_delivery"),
        _role("owner"),
        ("SELECT id::text, url, workspace_id::text", lambda stmts, params: [hook_row]),
        ("INSERT INTO workspace_webhook_delivery", insert_delivery),
        _no_rows("UPDATE workspace_webhook"),
    )
    _use_all(monkeypatch, conn, w, m)
    response = client.post(f"/api/v1/webhooks/{HOOK}/test")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["delivery"]["response_status"] == 200
    assert body["delivery"]["event_type"] == "test.ping"


def test_test_delivery_records_transport_failure(client, monkeypatch):
    import httpx

    def fail(url, body, headers):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(wd, "_post", fail)
    hook_row = (HOOK, "https://example.com/hook", WORKSPACE, b"cipher", True)

    def insert_delivery(stmts, params):
        assert params[3] is None
        assert params[5] is False
        assert "ConnectError" in params[6]
        return [("delivery-2", datetime.now(timezone.utc))]

    conn = _Conn(
        _regclass("workspace_webhook_delivery"),
        _role("owner"),
        ("SELECT id::text, url, workspace_id::text", lambda stmts, params: [hook_row]),
        ("INSERT INTO workspace_webhook_delivery", insert_delivery),
        _no_rows("UPDATE workspace_webhook"),
    )
    _use_all(monkeypatch, conn, w, m)
    response = client.post(f"/api/v1/webhooks/{HOOK}/test")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert "connection refused" in body["delivery"]["error"].lower()


def test_delivery_history_is_listed_newest_first(client, monkeypatch):
    ts = datetime.now(timezone.utc)
    rows = [
        ("d2", "test.ping", 500, "boom", False, "Receiver returned HTTP 500", 42, ts),
        ("d1", "test.ping", 200, "ok", True, None, 31, ts),
    ]
    conn = _Conn(_regclass("workspace_webhook_delivery"), ("SELECT id::text, event_type", lambda s, p: rows))
    _use(monkeypatch, w, conn)
    response = client.get(f"/api/v1/webhooks/{HOOK}/deliveries?limit=10")
    assert response.status_code == 200
    body = response.json()
    assert [d["id"] for d in body["deliveries"]] == ["d2", "d1"]
    assert body["deliveries"][0]["ok"] is False


def test_delivery_history_filter_is_parameterised(client, monkeypatch):
    conn = _Conn(_regclass("workspace_webhook_delivery"), ("SELECT id::text, event_type", lambda s, p: []))
    _use(monkeypatch, w, conn)
    response = client.get(f"/api/v1/webhooks/{HOOK}/deliveries?outcome=failed")
    assert response.status_code == 200
    sql, params = conn.cursor_obj.stmts[-1]
    assert "AND NOT ok" in sql
    assert params == (HOOK, 20)


def test_delete_unknown_webhook_returns_404(client, monkeypatch):
    conn = _Conn(_regclass("workspace_webhook"), _role("owner"), _no_rows("DELETE FROM workspace_webhook"))
    _use_all(monkeypatch, conn, w, m)
    response = client.delete(f"/api/v1/webhooks/{MISSING_HOOK}")
    assert response.status_code == 404


# ── Signature contract ───────────────────────────────────────────────────────


def test_signature_is_hmac_sha256_of_the_exact_body():
    import hmac

    webhook = {"id": HOOK, "workspace_id": WORKSPACE, "url": "https://example.com/hook"}
    payload = wd.build_payload(webhook, "test.ping", {"a": 1})
    body = wd.serialise(payload)
    signature = wd.sign_payload("whsec_test", body)
    expected = hmac.new(b"whsec_test", body, hashlib.sha256).hexdigest()
    assert signature == f"sha256={expected}"
    assert b'"event":"test.ping"' in body


def test_payload_is_deterministic_for_signature_verification():
    webhook = {"id": HOOK, "workspace_id": WORKSPACE, "url": "https://example.com/hook"}
    first = wd.serialise(wd.build_payload(webhook, "test.ping", {"b": 2, "a": 1}))
    second = wd.serialise(wd.build_payload(webhook, "test.ping", {"a": 1, "b": 2}))
    # sent_at differs by at most a second; compare the data segment only.
    assert first.split(b'"sent_at"')[0] == second.split(b'"sent_at"')[0]
