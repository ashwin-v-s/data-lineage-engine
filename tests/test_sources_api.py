"""Offline request-validation tests for the source-connection routes.

The router is mounted on a fresh FastAPI app and ``require_user`` is overridden
so no Supabase call or database connection is ever made.  These tests exercise
only the pure pydantic/path validation that runs before any database access.
"""
from __future__ import annotations

from contextlib import contextmanager

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import db as db_module
from backend.app.api.routes import membership
from backend.app.api.routes.sources import router
from backend.app.auth import require_user

sources_app = FastAPI()
sources_app.include_router(router, prefix="/api/v1")
sources_app.dependency_overrides[require_user] = lambda: {
    "id": "00000000-0000-0000-0000-000000000000"
}
client = TestClient(sources_app)

_WORKSPACE = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


class _RoleCursor:
    """Serves the two lookups ``require_role`` performs."""

    def __init__(self) -> None:
        self._row = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=()):
        if query.strip().startswith("SELECT to_regclass"):
            self._row = ("public.workspace_member",)
        else:
            self._row = ("editor",)

    def fetchone(self):
        return self._row


class _RoleConnection:
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def cursor(self, *_args, **_kwargs):
        return _RoleCursor()


class _WorkspaceContext:
    def get(self):
        return _WORKSPACE


@pytest.fixture(autouse=True)
def _signed_in_editor(monkeypatch):
    """Supply the authenticated workspace and role the guard reads.

    These offline tests exercise request validation, so the caller still has to
    be a real workspace member for the authorization gate to let the request
    reach validation.
    """

    @contextmanager
    def role_conn():
        yield _RoleConnection()

    monkeypatch.setattr(membership, "get_conn", role_conn)
    monkeypatch.setattr(db_module, "_workspace_id", _WorkspaceContext())


def _valid_payload() -> dict:
    return {
        "name": "warehouse",
        "source_kind": "postgresql",
        "host": "db.internal",
        "port": 5432,
        "dbname": "analytics",
        "user": "bob",
        "password": "s3cret",
        "schema_name": "public",
    }


@pytest.mark.parametrize("port", [0, 70000])
def test_create_rejects_an_out_of_range_port(port):
    payload = _valid_payload()
    payload["port"] = port
    res = client.post("/api/v1/sources", json=payload)
    assert res.status_code == 422, (res.status_code, res.text)


def test_create_rejects_an_unexpected_extra_field():
    payload = _valid_payload()
    payload["workspace_id"] = "11111111-1111-1111-1111-111111111111"
    res = client.post("/api/v1/sources", json=payload)
    assert res.status_code == 422, (res.status_code, res.text)


def test_get_rejects_a_malformed_id_instead_of_crashing():
    res = client.get("/api/v1/sources/not-a-uuid")
    assert res.status_code == 422, (res.status_code, res.text)


def test_create_rejects_an_unsupported_source_kind():
    payload = _valid_payload()
    payload["source_kind"] = "mysql"
    res = client.post("/api/v1/sources", json=payload)
    assert res.status_code == 422, (res.status_code, res.text)
