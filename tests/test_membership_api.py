"""Offline contract tests for the membership API (migration 0007 consumer).

No database contact: connections are fakes that answer scripted rows, and the
unprovisioned path (table missing) is exercised through the to_regclass guard.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app import db as dbmod
from backend.app.api.routes import membership as m
from backend.app.auth import require_user
from backend.app.main import app

USER = {"id": "user-1", "email": "tester@example.com"}
WORKSPACE = "11111111-1111-4111-8111-111111111111"


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
        raise AssertionError(f"Unexpected SQL in membership test: {sql[:120]}")

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


def _regclass(table: str):
    def handler(stmts, params):
        return [(table,)]

    return (f"to_regclass", handler)


def _members(*rows):
    def handler(stmts, params):
        return list(rows)

    return ("id::text", handler)


def _role(role: str):
    def handler(stmts, params):
        return [(role,)]

    return ("SELECT role", handler)


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
    monkeypatch.setattr(m, "get_conn", lambda: conn)
    return conn


# ── Provisioning guard ───────────────────────────────────────────────────────

def test_members_unprovisioned_returns_503(client, monkeypatch):
    conn = _Conn(_regclass(None))
    _use(monkeypatch, conn)
    response = client.get("/api/v1/members")
    assert response.status_code == 503
    assert "0007" in response.json()["detail"]
    assert conn.cursor_obj is not None
    assert not any("id::text" in sql for sql, _ in conn.cursor_obj.stmts)


def test_invites_unprovisioned_returns_503(client, monkeypatch):
    conn = _Conn(_regclass(None))
    _use(monkeypatch, conn)
    response = client.get("/api/v1/members/invites")
    assert response.status_code == 503


# ── Listing ──────────────────────────────────────────────────────────────────

def test_members_lists_active_rows(client, monkeypatch):
    ts = datetime.now(timezone.utc)
    conn = _Conn(
        _regclass("workspace_member"),
        _members(("m1", "user-1", "owner", "active", ts)),
    )
    _use(monkeypatch, conn)
    response = client.get("/api/v1/members")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["members"][0]["role"] == "owner"


# ── Role gate (roles come from the DB, never the JWT) ────────────────────────

def test_viewer_cannot_create_invite(client, monkeypatch):
    conn = _Conn(_regclass("workspace_member"), _role("viewer"))
    _use(monkeypatch, conn)
    response = client.post("/api/v1/members/invites", json={"email": "x@y.com", "role": "editor"})
    assert response.status_code == 403


def test_admin_can_create_invite(client, monkeypatch):
    def insert(stmts, params):
        assert params == ("x@y.com", "editor", "user-1")
        return [("invite-1",)]

    conn = _Conn(
        _regclass("workspace_member"),
        _role("admin"),
        _regclass("workspace_invite"),
        ("INSERT INTO workspace_invite", insert),
    )
    _use(monkeypatch, conn)
    response = client.post("/api/v1/members/invites", json={"email": "x@y.com", "role": "editor"})
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == "invite-1"
    assert "expires_at" in body


def test_invite_cannot_grant_ownership(client, monkeypatch):
    conn = _Conn(_regclass("workspace_member"), _role("owner"))
    _use(monkeypatch, conn)
    response = client.post("/api/v1/members/invites", json={"email": "x@y.com", "role": "owner"})
    assert response.status_code == 422


# ── Invite lifecycle ─────────────────────────────────────────────────────────

def _open_invite(expires_in: timedelta):
    def invite(stmts, params):
        return [("ws-1", "editor", datetime.now(timezone.utc) + expires_in, None)]

    return ("SELECT workspace_id", invite)


def test_accept_invite_joins_workspace(client, monkeypatch):
    conn = _Conn(
        _regclass("workspace_invite"),
        _open_invite(timedelta(days=1)),
        _regclass("workspace_member"),
        ("set_config", lambda stmts, params: [(params[0],)]),
        ("INSERT INTO workspace_member", lambda stmts, params: []),
        ("UPDATE workspace_invite", lambda stmts, params: []),
    )
    _use(monkeypatch, conn)
    response = client.post("/api/v1/members/invites/tok123/accept")
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "editor"
    assert body["workspace_id"] == "ws-1"


def test_accept_expired_invite_returns_410(client, monkeypatch):
    conn = _Conn(
        _regclass("workspace_invite"),
        _open_invite(timedelta(days=-1)),
    )
    _use(monkeypatch, conn)
    response = client.post("/api/v1/members/invites/tok123/accept")
    assert response.status_code == 410


def test_accept_unknown_invite_returns_404(client, monkeypatch):
    conn = _Conn(_regclass("workspace_invite"), ("SELECT workspace_id", lambda stmts, params: []))
    _use(monkeypatch, conn)
    response = client.post("/api/v1/members/invites/tok999/accept")
    assert response.status_code == 404
