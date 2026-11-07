from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import db as dbmod
from backend.app.api.routes import audit, workspaces
from backend.app.auth import require_user
from backend.app.main import app

USER = {"id": "11111111-1111-4111-8111-111111111111", "email": "owner@example.test"}
WORKSPACE = "22222222-2222-4222-8222-222222222222"


class _Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.sql = ""
        self.params = None

    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, sql, params=None): self.sql, self.params = sql, params
    def fetchall(self): return self.rows


class _Conn:
    def __init__(self, rows): self.cursor_value = _Cursor(rows)
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def cursor(self, *args, **kwargs): return self.cursor_value


def _client():
    app.dependency_overrides[require_user] = lambda: USER
    return TestClient(app)


def test_workspace_list_uses_verified_user_id_and_returns_current_scope(monkeypatch):
    token = dbmod.set_workspace_id(WORKSPACE)
    conn = _Conn([(WORKSPACE, "Demo workspace", "owner", True)])
    monkeypatch.setattr(workspaces, "get_conn", lambda: conn)
    client = _client()
    try:
        response = client.get("/api/v1/me/workspaces")
    finally:
        app.dependency_overrides.pop(require_user, None)
        dbmod.reset_workspace_id(token)
    assert response.status_code == 200
    assert response.json()["workspaces"] == [{"id": WORKSPACE, "name": "Demo workspace", "role": "owner", "current": True}]


def test_workspace_audit_returns_scoped_change_summary_without_values(monkeypatch):
    token = dbmod.set_workspace_id(WORKSPACE)
    entry = {"id": "audit-1", "asset_id": "asset-1", "asset_name": "orders", "field_name": "description", "changed_by": "owner", "change_type": "UPDATE", "change_reason": "Documentation", "created_at": "2026-11-07T00:00:00Z"}
    conn = _Conn([entry])
    monkeypatch.setattr(audit, "get_conn", lambda: conn)
    client = _client()
    try:
        response = client.get("/api/v1/audit/workspace?limit=10")
    finally:
        app.dependency_overrides.pop(require_user, None)
        dbmod.reset_workspace_id(token)
    assert response.status_code == 200
    assert response.json()["entries"] == [entry]
    assert "old_value" not in conn.cursor_value.sql
    assert "new_value" not in conn.cursor_value.sql
    assert conn.cursor_value.params == (10, 0)
