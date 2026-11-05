"""Contract tests for the read-only import-run history endpoints.

The API is fail-closed: the ingest router requires a verified Supabase session
and a workspace-scoped database connection.  The offline tests therefore
override ``require_user`` and assert the *pure request-validation* behaviour
(``limit``/``offset`` bounds, malformed ``import_id``) that never reaches the
database.  The database-backed reads are gated behind the same opt-in used by
``tests/test_live_api.py`` (``KAIROS_LIVE_API_TESTS=1`` plus a user token).
"""
from __future__ import annotations

import os
import uuid

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from backend.app.auth import require_user
from backend.app.main import app
from tests.conftest import requires_live_backend

client = TestClient(app)


@pytest.fixture
def authenticated():
    """TestClient with a stubbed authenticated user (no Supabase, no DB)."""
    app.dependency_overrides[require_user] = lambda: {"id": "00000000-0000-0000-0000-000000000000"}
    try:
        yield client
    finally:
        app.dependency_overrides.pop(require_user, None)


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}])
def test_list_runs_rejects_out_of_range_pagination(authenticated, params):
    res = authenticated.get("/api/v1/ingest/runs", params=params)
    assert res.status_code == 422, (params, res.status_code, res.text)


def test_get_run_rejects_a_malformed_id_instead_of_crashing(authenticated):
    res = authenticated.get("/api/v1/ingest/runs/not-a-uuid")
    assert res.status_code == 422, (res.status_code, res.text)


def _operator_token() -> str | None:
    """The bearer token an operator supplies to run the live tests."""
    token = os.getenv("KAIROS_TEST_USER_TOKEN", "").strip()
    return token or None


def _live_client() -> TestClient:
    return TestClient(app, headers={"Authorization": f"Bearer {_operator_token()}"})


@requires_live_backend
@pytest.mark.skipif(
    _operator_token() is None,
    reason="Set KAIROS_TEST_USER_TOKEN to run the live ingest-run tests.",
)
def test_list_runs_live_returns_runs_and_count():
    res = _live_client().get("/api/v1/ingest/runs", params={"limit": 5})
    assert res.status_code == 200, res.text
    body = res.json()
    assert isinstance(body.get("runs"), list)
    assert isinstance(body.get("count"), int)
    assert body["count"] == len(body["runs"])


@requires_live_backend
@pytest.mark.skipif(
    _operator_token() is None,
    reason="Set KAIROS_TEST_USER_TOKEN to run the live ingest-run tests.",
)
def test_get_run_live_unknown_id_returns_404():
    res = _live_client().get(f"/api/v1/ingest/runs/{uuid.uuid4()}")
    assert res.status_code == 404, res.text
