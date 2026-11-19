"""Offline contract tests for the stewardship API (migration 0017 consumer).

No database contact: connections are fakes that answer scripted rows, and the
unprovisioned path (table missing) is exercised through the to_regclass guard.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app import db as dbmod
from backend.app.api.routes import membership as membership_routes
from backend.app.api.routes import stewardship as st
from backend.app.auth import require_user
from backend.app.main import app

USER = {"id": "11111111-1111-4111-8111-aaaaaaaaaaaa", "email": "steward@example.com"}
ADMIN = {"id": "22222222-2222-4222-8222-bbbbbbbbbbbb", "email": "owner@example.com"}
WORKSPACE = "11111111-1111-4111-8111-111111111111"
REQUEST_ID = "33333333-3333-4333-8333-cccccccccccc"
DATASET_ID = "44444444-4444-4444-8444-dddddddddddd"
NOW = datetime(2026, 11, 19, 9, 30, tzinfo=timezone.utc)


class _Cursor:
    def __init__(self, conn):
        self.conn = conn
        self.stmts: list[tuple[str, tuple | None]] = []
        self.rowcount = 0
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
        raise AssertionError(f"Unexpected SQL in stewardship test: {sql[:140]}")

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
    def handler(stmts, params):
        return [(table,)]

    return ("to_regclass", handler)


def _role(role: str):
    def handler(stmts, params):
        return [(role,)]

    return ("SELECT role", handler)


def _request_row(status="PENDING", kind="access", note=None, resolved_at=None):
    return (
        REQUEST_ID, kind, DATASET_ID, "public.orders", None if kind == "access" else "order value",
        "Need access to reconcile revenue.", USER["id"], USER["email"], status, note,
        ADMIN["id"] if status != "PENDING" else None, resolved_at, NOW, NOW,
    )


def _list(*rows):
    def handler(stmts, params):
        return list(rows)

    return ("FROM stewardship_request", handler)


def _insert(*rows):
    def handler(stmts, params):
        return list(rows) or [_request_row()]

    return ("INSERT INTO stewardship_request", handler)


def _status(status: str | None):
    def handler(stmts, params):
        return [] if status is None else [(status,)]

    return ("SELECT status FROM stewardship_request", handler)


def _update(*rows):
    def handler(stmts, params):
        return list(rows)

    return ("UPDATE stewardship_request", handler)


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


def _use(monkeypatch, conn):
    monkeypatch.setattr(st, "get_conn", lambda: conn)
    # The role guard resolves membership.get_conn at call time.
    monkeypatch.setattr(membership_routes, "get_conn", lambda: conn)
    return conn


# ── Provisioning guard ───────────────────────────────────────────────────────

def test_requests_unprovisioned_returns_503(client, monkeypatch):
    _use(monkeypatch, _Conn(_regclass(None)))
    response = client.get("/api/v1/stewardship/requests")
    assert response.status_code == 503
    assert "0017" in response.text


def test_create_unprovisioned_returns_503(client, monkeypatch):
    _use(monkeypatch, _Conn(_regclass(None)))
    response = client.post(
        "/api/v1/stewardship/requests",
        json={"kind": "access", "asset_label": "public.orders", "detail": "Need access"},
    )
    assert response.status_code == 503


# ── Creation ─────────────────────────────────────────────────────────────────

def test_create_access_request(client, monkeypatch):
    conn = _use(monkeypatch, _Conn(_regclass("stewardship_request"), _insert()))
    response = client.post(
        "/api/v1/stewardship/requests",
        json={"kind": "access", "dataset_id": DATASET_ID, "asset_label": "public.orders", "detail": " Need access "},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["request"]["status"] == "PENDING"
    assert body["request"]["kind"] == "access"
    insert_params = [p for sql, p in conn.cursor_obj.stmts if "INSERT INTO stewardship_request" in sql][0]
    assert insert_params[0] == "access"
    assert insert_params[1] == DATASET_ID
    assert insert_params[2] == "public.orders"
    assert insert_params[4] == "Need access"  # trimmed
    assert insert_params[5] == USER["id"]
    assert insert_params[6] == USER["email"]


def test_create_glossary_proposal(client, monkeypatch):
    _use(monkeypatch, _Conn(_regclass("stewardship_request"), _insert(_request_row(kind="glossary"))))
    response = client.post(
        "/api/v1/stewardship/requests",
        json={"kind": "glossary", "title": "order value", "detail": "Definition for the revenue team"},
    )
    assert response.status_code == 201
    assert response.json()["request"]["title"] == "order value"


def test_access_request_requires_an_asset(client, monkeypatch):
    _use(monkeypatch, _Conn(_regclass("stewardship_request")))
    response = client.post(
        "/api/v1/stewardship/requests",
        json={"kind": "access", "detail": "Need access"},
    )
    assert response.status_code == 422
    assert "asset" in response.text.lower()


def test_glossary_proposal_requires_a_term(client, monkeypatch):
    _use(monkeypatch, _Conn(_regclass("stewardship_request")))
    response = client.post(
        "/api/v1/stewardship/requests",
        json={"kind": "glossary", "detail": "Definition without a name"},
    )
    assert response.status_code == 422


def test_empty_detail_is_rejected(client, monkeypatch):
    _use(monkeypatch, _Conn(_regclass("stewardship_request")))
    response = client.post(
        "/api/v1/stewardship/requests",
        json={"kind": "access", "asset_label": "public.orders", "detail": "   "},
    )
    assert response.status_code == 422


def test_api_key_principal_cannot_raise_requests(workspace_scope, monkeypatch):
    app.dependency_overrides[require_user] = lambda: {"id": "api-key:abc", "auth": "api_key", "workspace_id": WORKSPACE}
    _use(monkeypatch, _Conn(_regclass("stewardship_request")))
    try:
        response = TestClient(app).post(
            "/api/v1/stewardship/requests",
            json={"kind": "access", "asset_label": "public.orders", "detail": "Need access"},
        )
    finally:
        app.dependency_overrides.pop(require_user, None)
    assert response.status_code == 403
    assert "signed-in member" in response.text


# ── Listing ──────────────────────────────────────────────────────────────────

def test_list_returns_counts(client, monkeypatch):
    conn = _use(
        monkeypatch,
        _Conn(
            _regclass("stewardship_request"),
            _list(_request_row(), _request_row(status="APPROVED", resolved_at=NOW), _request_row(status="REJECTED", resolved_at=NOW)),
        ),
    )
    response = client.get("/api/v1/stewardship/requests")
    assert response.status_code == 200
    body = response.json()
    assert body["counts"] == {"PENDING": 1, "APPROVED": 1, "REJECTED": 1}
    assert body["count"] == 3
    list_sql, list_params = [x for x in conn.cursor_obj.stmts if "FROM stewardship_request" in x[0]][0]
    assert "ORDER BY (status = 'PENDING') DESC" in list_sql
    assert list_params == (100,)


def test_list_filters_by_status_and_kind(client, monkeypatch):
    conn = _use(monkeypatch, _Conn(_regclass("stewardship_request"), _list(_request_row())))
    response = client.get("/api/v1/stewardship/requests?status=pending&kind=access&limit=25")
    assert response.status_code == 200
    list_sql, list_params = [x for x in conn.cursor_obj.stmts if "FROM stewardship_request" in x[0]][0]
    assert "AND status = %s" in list_sql
    assert "AND kind = %s" in list_sql
    assert list_params == ("PENDING", "access", 25)


# ── Resolution ───────────────────────────────────────────────────────────────

def test_owner_can_approve_pending_request(client, monkeypatch):
    conn = _use(
        monkeypatch,
        _Conn(
            _regclass("stewardship_request"),
            _role("owner"),
            _status("PENDING"),
            _update(_request_row(status="APPROVED", resolved_at=NOW)),
        ),
    )
    response = client.post(f"/api/v1/stewardship/requests/{REQUEST_ID}/approve", json={"note": "Approved for the quarter"})
    assert response.status_code == 200
    assert response.json()["request"]["status"] == "APPROVED"
    update_sql, update_params = [x for x in conn.cursor_obj.stmts if "UPDATE stewardship_request" in x[0]][0]
    assert update_params[0] == "APPROVED"
    assert update_params[1] == "Approved for the quarter"
    assert update_params[2] == USER["id"]
    assert update_params[3] == REQUEST_ID


def test_admin_can_reject_with_note(client, monkeypatch):
    _use(
        monkeypatch,
        _Conn(
            _regclass("stewardship_request"),
            _role("admin"),
            _status("PENDING"),
            _update(_request_row(status="REJECTED", note="Use the reporting mart instead", resolved_at=NOW)),
        ),
    )
    response = client.post(f"/api/v1/stewardship/requests/{REQUEST_ID}/reject", json={"note": "Use the reporting mart instead"})
    assert response.status_code == 200
    body = response.json()["request"]
    assert body["status"] == "REJECTED"
    assert body["resolution_note"] == "Use the reporting mart instead"


def test_viewer_cannot_resolve_requests(client, monkeypatch):
    _use(monkeypatch, _Conn(_regclass("stewardship_request"), _role("viewer")))
    response = client.post(f"/api/v1/stewardship/requests/{REQUEST_ID}/approve")
    assert response.status_code == 403


def test_resolving_an_unknown_request_returns_404(client, monkeypatch):
    _use(monkeypatch, _Conn(_regclass("stewardship_request"), _role("owner"), _status(None)))
    response = client.post(f"/api/v1/stewardship/requests/{REQUEST_ID}/approve")
    assert response.status_code == 404


def test_resolving_a_resolved_request_returns_409(client, monkeypatch):
    _use(monkeypatch, _Conn(_regclass("stewardship_request"), _role("owner"), _status("APPROVED")))
    response = client.post(f"/api/v1/stewardship/requests/{REQUEST_ID}/reject")
    assert response.status_code == 409
