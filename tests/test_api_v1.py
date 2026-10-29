"""Offline contract tests for the Kairos API layer.

The API is fail-closed: every route except ``/api/v1/auth/config`` requires a
verified Supabase session (see ``backend/app/auth.py::require_user``) and a
workspace-scoped database connection.  These tests therefore assert the
*contract* — the public endpoint, the route inventory, and the fail-closed
error envelope — without needing a live Supabase project.

Integration tests that exercise real data are gated by
``tests.conftest.requires_live_backend`` (opt in with ``KAIROS_LIVE_API_TESTS=1``).
"""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.auth import require_user
from backend.app.services import github_app

client = TestClient(app)

# "You are not allowed in": 401 when Supabase is configured but no token was
# supplied, 503 when authentication is not configured at all.
_FAIL_CLOSED_STATUS = {401, 503}
_FAIL_CLOSED_CODES = {"UNAUTHENTICATED", "AUTH_UNAVAILABLE"}


def _assert_error_envelope(response):
    """Every API error must use the single, stable ``{"error": {...}}`` shape."""
    body = response.json()
    assert set(body) == {"error"}, body
    assert set(body["error"]) == {"code", "message", "request_id"}, body
    assert isinstance(body["error"]["request_id"], str) and body["error"]["request_id"]
    assert "X-Request-ID" in response.headers
    return body["error"]


def test_auth_config_is_public_and_fails_closed():
    res = client.get("/api/v1/auth/config")
    assert res.status_code == 200
    body = res.json()
    assert set(body) == {"url", "publishable_key", "auth_disabled"}
    # Authentication must never be silently disabled by the server config.
    assert body["auth_disabled"] is False


def test_liveness_healthz_is_public_and_needs_no_credentials():
    """GET /healthz is the unauthenticated probe hosting platforms poll."""
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "service": "kairos-api"}


_PROTECTED_PATHS = [
    "/api/v1/health",
    "/api/v1/search",
    "/api/v1/catalog",
    "/api/v1/assets/anything",
    "/api/v1/assets/anything/lineage",
    "/api/v1/lineage/anything/upstream",
    "/api/v1/evidence-at-time?valid_as_of=2026-01-01T00:00:00Z",
    "/api/v1/column-lineage",
    "/api/v1/runs/run_x/dependency/a/b",
    "/api/v1/owner/team-members",
    "/api/v1/owner/stats/overview",
    "/api/v1/audit/anything/trail",
    "/api/v1/audit/anything/versions",
    "/api/v1/metadata/anything/editable",
    "/api/v1/rea/recommendations",
    "/api/v1/raw-events",
    "/api/v1/me/recently-viewed",
    "/api/v1/me/starred-assets",
    "/api/v1/assets/anything/downstream-impact",
    "/api/v1/integrations/github/status",
]


@pytest.mark.parametrize("path", _PROTECTED_PATHS)
def test_protected_routes_fail_closed_without_a_session(path):
    res = client.get(path)
    assert res.status_code in _FAIL_CLOSED_STATUS, (path, res.status_code, res.text)
    error = _assert_error_envelope(res)
    assert error["code"] in _FAIL_CLOSED_CODES


def test_unknown_path_uses_the_stable_not_found_envelope():
    res = client.get("/api/v1/this-route-does-not-exist")
    assert res.status_code == 404
    error = _assert_error_envelope(res)
    assert error["code"] == "NOT_FOUND"


def test_github_connector_status_reports_the_configuration_shape(monkeypatch):
    """An authenticated caller sees exactly the connector status contract."""
    for name in github_app.GITHUB_ENV_VARS:
        monkeypatch.delenv(name, raising=False)

    app.dependency_overrides[require_user] = lambda: {"id": "test-user"}
    try:
        res = client.get("/api/v1/integrations/github/status")
    finally:
        app.dependency_overrides.pop(require_user, None)

    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body) == {
        "configured",
        "missing_env",
        "token_encryption_configured",
        "read_only",
        "install_url",
    }
    assert body["configured"] is False
    assert body["missing_env"]


def test_oversized_request_body_is_rejected_before_routing(monkeypatch):
    monkeypatch.setattr("backend.app.main.MAX_REQUEST_BYTES", 128)
    payload = {"asset_ids": ["x" * 500]}
    res = client.post("/api/v1/metadata/bulk-update", json=payload)
    assert res.status_code == 413, (res.status_code, res.text)
    error = _assert_error_envelope(res)
    assert error["code"] == "PAYLOAD_TOO_LARGE"


def test_openapi_exposes_the_expected_route_inventory():
    paths = app.openapi()["paths"]
    expected = {
        "/api/v1/auth/config",
        "/api/v1/health",
        "/api/v1/search",
        "/api/v1/catalog",
        "/api/v1/assets/{asset_id}",
        "/api/v1/assets/{asset_id}/lineage",
        "/api/v1/lineage/{asset_id}/{direction}",
        "/api/v1/evidence-at-time",
        "/api/v1/column-lineage",
        "/api/v1/runs/{run_id}/dependency/{source}/{target}",
        "/api/v1/owner/team-members",
        "/api/v1/owner/assign/{asset_id}",
        "/api/v1/audit/{asset_id}/trail",
        "/api/v1/audit/{asset_id}/export-audit",
        "/api/v1/metadata/{asset_id}/editable",
        "/api/v1/raw-events",
        "/api/v1/rea/recommendations",
        "/api/v1/me/recently-viewed",
        "/api/v1/me/recently-viewed/{asset_id}",
        "/api/v1/me/starred-assets",
        "/api/v1/assets/{asset_id}/star",
        "/api/v1/assets/{asset_id}/downstream-impact",
    }
    missing = expected - set(paths)
    assert not missing, f"Routes missing from the OpenAPI schema: {sorted(missing)}"
