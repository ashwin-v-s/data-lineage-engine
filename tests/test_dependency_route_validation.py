"""Regression tests for the dependency-state route's boundary handling.

Two defects are covered:

* an unresolvable ``source``/``target`` used to be interpolated into
  ``%s::uuid`` evidence queries, so a missing asset produced an opaque HTTP 500
  (PostgreSQL 22P02) instead of a clear 404; and
* ``as_of`` / ``recorded_as_of`` were passed straight to ``::timestamptz``, so a
  malformed timestamp also produced a 500 instead of a 422.

Neither case may reach the database with a bad value.
"""
from __future__ import annotations

from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from backend.app.api.routes import dependency
from backend.app.auth import require_user
from backend.app.main import app

client = TestClient(app)


class _Cursor:
    """Returns the run row, then nothing for every identifier lookup."""

    def __init__(self) -> None:
        self._rows: list = []
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=()):
        if "FROM execution_run" in query:
            self._rows = [{"run_id": "run-1", "status": "completed"}]
        else:
            self._rows = []

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None

    def fetchall(self):
        return []


class _Connection:
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def cursor(self, *_args, **_kwargs):
        return _Cursor()


@pytest.fixture(autouse=True)
def _signed_in(monkeypatch):
    app.dependency_overrides[require_user] = lambda: {"id": "test-user"}
    yield
    app.dependency_overrides.pop(require_user, None)


def test_unknown_column_identifier_is_a_404_not_a_database_error(monkeypatch):
    @contextmanager
    def conn():
        yield _Connection()

    monkeypatch.setattr(dependency, "get_conn", conn)

    response = client.get("/api/v1/runs/run-1/dependency/missing_column/other_column")

    assert response.status_code == 404, response.text
    body = response.json()
    message = body.get("detail") or body.get("error", {}).get("message", "")
    assert "not found" in message.lower()


@pytest.mark.parametrize("field", ["as_of", "recorded_as_of"])
def test_malformed_timestamp_is_rejected_with_422(field):
    response = client.get(
        "/api/v1/runs/run-1/dependency/orders/order_items",
        params={field: "not-a-timestamp"},
    )

    assert response.status_code == 422, response.text
    body = response.json()
    detail = body.get("detail") or body.get("error", {}).get("message", "")
    assert field in str(detail)
