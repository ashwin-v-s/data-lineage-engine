"""Authorization contract for the ownership routes.

Assigning an owner writes dataset metadata, so a viewer must be refused before
any write happens, while an editor is allowed through to the handler.  The
approval endpoint is owner/admin only and refuses self-approval.

No database contact: the role lookup and the handler connection are fakes.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app import db as dbmod
from backend.app.api.routes import membership as m
from backend.app.api.routes import owner as o
from backend.app.auth import require_user
from backend.app.main import app

USER = {"id": "user-1", "email": "tester@example.com"}
WORKSPACE = "11111111-1111-4111-8111-111111111111"
ASSET = "22222222-2222-4222-8222-222222222222"
REQUEST = "33333333-3333-4333-8333-333333333333"


class _Cursor:
    def __init__(self, row):
        self.row = row
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, sql, params=None):
        return None

    def fetchone(self):
        return self.row

    def fetchall(self):
        return [self.row] if self.row else []

    def close(self):
        pass


class _Conn:
    def __init__(self, row):
        self.row = row

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def cursor(self, *args, **kwargs):
        return _Cursor(self.row)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


class _RoleConn:
    """Answers the to_regclass guard and the role lookup require_role issues."""

    def __init__(self, role: str):
        self.role = role

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def cursor(self, *args, **kwargs):
        return _RoleCursor(self.role)

    def commit(self):
        pass

    def rollback(self):
        pass


class _RoleCursor:
    def __init__(self, role: str):
        self.role = role
        self._rows = []

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, sql, params=None):
        if "to_regclass" in sql:
            self._rows = [("workspace_member",)]
        elif "SELECT role" in sql:
            self._rows = [(self.role,)]
        else:  # pragma: no cover - defensive
            raise AssertionError(f"Unexpected SQL in role guard: {sql[:80]}")

    def fetchone(self):
        return self._rows[0] if self._rows else None


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


def test_viewer_cannot_assign_an_owner(client, monkeypatch):
    monkeypatch.setattr(m, "get_conn", lambda: _RoleConn("viewer"))
    monkeypatch.setattr(
        o, "get_db_connection", lambda: pytest.fail("a viewer must not reach the write path")
    )
    response = client.post(
        f"/api/v1/owner/assign/{ASSET}",
        json={"owner_email": "someone@example.com", "reason": "reorg"},
    )
    assert response.status_code == 403


def test_editor_reaches_the_assignment_handler(client, monkeypatch):
    monkeypatch.setattr(m, "get_conn", lambda: _RoleConn("editor"))
    monkeypatch.setattr(o, "get_db_connection", lambda: _Conn(None))
    response = client.post(
        f"/api/v1/owner/assign/{ASSET}",
        json={"owner_email": "someone@example.com", "reason": "reorg"},
    )
    # Past the gate: the fake dataset does not exist, so the handler answers 404.
    assert response.status_code == 404


def test_editor_cannot_approve_an_owner_request(client, monkeypatch):
    monkeypatch.setattr(m, "get_conn", lambda: _RoleConn("editor"))
    monkeypatch.setattr(
        o, "get_db_connection", lambda: pytest.fail("an editor must not approve ownership changes")
    )
    response = client.post(f"/api/v1/owner/requests/{REQUEST}/approve", json={"reason": "ok"})
    assert response.status_code == 403


def test_requester_cannot_approve_their_own_request(client, monkeypatch):
    monkeypatch.setattr(m, "get_conn", lambda: _RoleConn("owner"))

    def no_write():
        raise AssertionError("rollback check should short-circuit before any write")

    pending = {
        "id": REQUEST,
        "status": "PENDING",
        "is_active": True,
        "requested_by": USER["email"],
        "requested_owner": "someone@example.com",
        "dataset_id": ASSET,
        "reason": "reorg",
    }
    monkeypatch.setattr(o, "get_db_connection", lambda: _Conn(pending))
    try:
        response = client.post(f"/api/v1/owner/requests/{REQUEST}/approve", json={"reason": "ok"})
    except AssertionError as exc:  # pragma: no cover - only if the guard is missing
        pytest.fail(str(exc))
    assert response.status_code == 403
    assert "raised" in response.json()["detail"].lower()
