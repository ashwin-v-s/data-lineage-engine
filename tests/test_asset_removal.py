"""API contract tests for workspace-scoped asset soft removal."""
from __future__ import annotations

from contextlib import contextmanager

from fastapi.testclient import TestClient

from backend.app.api.routes import assets
from backend.app.auth import require_user
from backend.app.main import app

ASSET_ID = "77777777-7777-4777-8777-777777777777"
USER_ID = "44444444-4444-4444-8444-444444444444"


class _Cursor:
    def __init__(self, *, found=True):
        self.rowcount = 0
        self.found = found
        self.statements = []
        self._one = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=()):
        sql = " ".join(query.split())
        self.statements.append((sql, params))
        if sql.startswith("SELECT asset_id::text AS id, asset_name AS name"):
            self._one = {"id": ASSET_ID, "name": "orders"} if self.found else None

    def fetchone(self):
        return self._one


class _Connection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def cursor(self, *_args, **_kwargs):
        return self._cursor


def _client(monkeypatch, *, found=True):
    cursor = _Cursor(found=found)

    @contextmanager
    def get_conn():
        yield _Connection(cursor)

    monkeypatch.setattr(assets, "get_conn", get_conn)
    app.dependency_overrides[require_user] = lambda: {"id": USER_ID}
    app.dependency_overrides[assets.remove_asset_role] = lambda: {"id": USER_ID}
    return TestClient(app), cursor


def test_remove_asset_hides_asset_and_records_audit(monkeypatch):
    client, cursor = _client(monkeypatch)
    try:
        response = client.delete(f"/api/v1/assets/{ASSET_ID}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["removed"] is True
    sql = [statement for statement, _params in cursor.statements]
    assert any("public.kairos_remove_dataset" in statement for statement in sql)
    assert not any(statement.startswith("DELETE FROM") for statement in sql)


def test_remove_asset_returns_not_found_for_missing_active_asset(monkeypatch):
    client, cursor = _client(monkeypatch, found=False)
    try:
        response = client.delete(f"/api/v1/assets/{ASSET_ID}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert len(cursor.statements) == 1
