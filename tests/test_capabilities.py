"""Tests for the per-asset capability registry.

Two groups:

A. Pure unit tests of ``resolve_capabilities`` -- the decision policy, which is
   deliberately database-free so it can be verified offline.
B. Offline HTTP validation tests.  The endpoint is mounted on a fresh app (the
   capabilities router is not yet registered in ``backend.app.main``) and the
   database connection is stubbed, so nothing here talks to Supabase.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.routes import capabilities as capabilities_module
from backend.app.api.routes.capabilities import CAPABILITY_KEYS, resolve_capabilities, router
from backend.app.auth import require_user

_ENTRY_KEYS = {"supported", "available", "reason"}


def _resolved(**overrides) -> dict[str, dict]:
    """Call the resolver with all-available defaults unless overridden."""
    facts = {
        "has_columns": True,
        "edge_count": 1,
        "run_count": 1,
        "quality_supported": True,
        "quality_available": True,
        "profile_supported": True,
    }
    facts.update(overrides)
    return resolve_capabilities(**facts)


# ── Group A: pure policy tests ────────────────────────────────────────────────

def test_every_capability_key_is_present():
    result = _resolved()
    assert set(result) == set(CAPABILITY_KEYS)


def test_quality_lookup_uses_the_proposed_assertion_result_relationship():
    class SchemaCursor:
        def __init__(self):
            self.query = ""
            self.params = None
            self._row = None

        def execute(self, query, params=()):
            self.query = " ".join(query.split())
            self.params = params
            if "to_regclass" in self.query:
                self._row = {"reg": "public.quality_assertion" if "quality_assertion" in params[0] else "public.quality_result"}
            else:
                self._row = {"has_quality": True}

        def fetchone(self):
            return self._row

    cur = SchemaCursor()
    assert capabilities_module._quality_facts(cur, "11111111-1111-4111-8111-111111111111") == (True, True)
    assert "JOIN quality_assertion qa ON qa.id = qr.assertion_id" in cur.query
    assert "qa.dataset_id = %s::uuid" in cur.query
    assert "quality_result WHERE dataset_id" not in cur.query
    assert cur.params == ("11111111-1111-4111-8111-111111111111",)


def test_every_entry_has_exactly_the_three_keys():
    for key, entry in _resolved().items():
        assert set(entry) == _ENTRY_KEYS, (key, entry)


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {"has_columns": False},
        {"edge_count": 0},
        {"run_count": 0},
        {"quality_supported": False, "quality_available": False},
        {"quality_supported": True, "quality_available": False},
        {"profile_supported": False},
        {"has_columns": False, "edge_count": 0, "run_count": 0, "quality_supported": False,
         "quality_available": False, "profile_supported": False},
    ],
)
def test_reason_is_none_if_and_only_if_available(overrides):
    for key, entry in _resolved(**overrides).items():
        assert (entry["reason"] is None) is (entry["available"] is True), (key, entry)


def test_schema_unavailable_without_columns():
    entry = _resolved(has_columns=False)["schema"]
    assert entry["supported"] is True
    assert entry["available"] is False
    assert entry["reason"]


def test_preview_unavailable_without_columns():
    entry = _resolved(has_columns=False)["preview"]
    assert entry["supported"] is True
    assert entry["available"] is False
    assert entry["reason"]


def test_lineage_without_edges_does_not_assert_no_relationships_exist():
    entry = _resolved(edge_count=0)["lineage"]
    assert entry["supported"] is True
    assert entry["available"] is False
    assert entry["reason"] is not None
    assert "No evidence" in entry["reason"]


def test_lineage_with_edges_is_available():
    entry = _resolved(edge_count=3)["lineage"]
    assert entry["available"] is True
    assert entry["reason"] is None


def test_runs_unavailable_without_runs():
    entry = _resolved(run_count=0)["runs"]
    assert entry["supported"] is True
    assert entry["available"] is False
    assert entry["reason"]


def test_quality_unsupported_when_governance_migration_absent():
    entry = _resolved(quality_supported=False, quality_available=False)["quality"]
    assert entry["supported"] is False
    assert entry["available"] is False
    assert entry["reason"]


def test_quality_supported_but_no_results():
    entry = _resolved(quality_supported=True, quality_available=False)["quality"]
    assert entry["supported"] is True
    assert entry["available"] is False
    assert entry["reason"]


def test_profile_needs_columns_and_deployment_support():
    unsupported = _resolved(profile_supported=False)["profile"]
    assert unsupported["supported"] is False
    assert unsupported["available"] is False
    assert unsupported["reason"]

    no_columns = _resolved(profile_supported=True, has_columns=False)["profile"]
    assert no_columns["supported"] is True
    assert no_columns["available"] is False
    assert no_columns["reason"]

    ready = _resolved(profile_supported=True, has_columns=True)["profile"]
    assert ready["available"] is True
    assert ready["reason"] is None


def test_usage_is_never_supported():
    for overrides in ({}, {"has_columns": False}, {"edge_count": 0}):
        entry = _resolved(**overrides)["usage"]
        assert entry["supported"] is False
        assert entry["available"] is False
        assert entry["reason"]


def test_resolver_is_deterministic():
    assert _resolved() == _resolved()
    assert _resolved(has_columns=False) == _resolved(has_columns=False)


# ── Group B: offline HTTP validation tests ────────────────────────────────────

class _FakeCursor:
    """Minimal cursor whose every lookup misses (asset does not exist)."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, *args, **kwargs):
        return None

    def fetchone(self):
        return None

    def fetchall(self):
        return []


class _FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, *args, **kwargs):
        return _FakeCursor()


@pytest.fixture
def authenticated_app(monkeypatch):
    """A fresh app with the router mounted and auth + DB stubbed (no network)."""
    monkeypatch.setattr(capabilities_module, "get_conn", lambda: _FakeConnection())
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[require_user] = lambda: {"id": "00000000-0000-0000-0000-000000000000"}
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(require_user, None)


@pytest.mark.parametrize("asset_id", ["not-a-uuid", "00000000-0000-0000-0000-000000000000"])
def test_unknown_asset_never_crashes(authenticated_app, asset_id):
    res = authenticated_app.get(f"/api/v1/assets/{asset_id}/capabilities")
    assert res.status_code in (404, 422), (asset_id, res.status_code, res.text)
    assert res.status_code != 500


def test_requires_authentication(monkeypatch):
    # Configure an auth URL so the missing bearer token yields 401 (not the 503
    # "authentication is not configured" path) without any network call.
    monkeypatch.setenv("SUPABASE_URL", "http://auth.invalid")
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    client = TestClient(app)
    res = client.get("/api/v1/assets/not-a-uuid/capabilities")
    assert res.status_code in (401, 403), (res.status_code, res.text)
