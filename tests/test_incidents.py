"""Offline contract tests for the governance API router.

The governance migration (``0009_governance.sql``) is proposal-only and is not
applied to the shared Supabase project, so live database tests would fail — that
is expected.  These tests therefore mount the router on a fresh app, override
``require_user``, and assert only the *pure request-validation* behaviour that
never reaches the database.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.routes.governance import router
from backend.app.auth import require_user
from backend.app.services.freshness import next_incident_status

_USER = {"id": "11111111-1111-1111-1111-111111111111"}

_SLA = {
    "asset_id": "orders",
    "warn_after_minutes": 60,
    "error_after_minutes": 120,
    "signal": "openlineage_run",
}


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[require_user] = lambda: dict(_USER)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(require_user, None)


def test_sla_rejects_error_not_greater_than_warn(client):
    payload = {**_SLA, "warn_after_minutes": 120, "error_after_minutes": 60}
    res = client.post("/api/v1/governance/slas", json=payload)
    assert res.status_code == 422, (res.status_code, res.text)


def test_sla_rejects_equal_warn_and_error(client):
    payload = {**_SLA, "warn_after_minutes": 60, "error_after_minutes": 60}
    res = client.post("/api/v1/governance/slas", json=payload)
    assert res.status_code == 422, (res.status_code, res.text)


def test_sla_rejects_zero_warn_after_minutes(client):
    payload = {**_SLA, "warn_after_minutes": 0}
    res = client.post("/api/v1/governance/slas", json=payload)
    assert res.status_code == 422, (res.status_code, res.text)


def test_sla_rejects_unknown_field(client):
    payload = {**_SLA, "unexpected_field": "boom"}
    res = client.post("/api/v1/governance/slas", json=payload)
    assert res.status_code == 422, (res.status_code, res.text)


def test_evaluate_rejects_malformed_asset_id(client):
    res = client.post("/api/v1/governance/datasets/not-a-uuid/evaluate")
    assert res.status_code == 422, (res.status_code, res.text)


def test_incident_detail_rejects_malformed_id(client):
    res = client.get("/api/v1/governance/incidents/not-a-uuid")
    assert res.status_code == 422, (res.status_code, res.text)


def test_next_incident_status_rejects_illegal_transition():
    with pytest.raises(ValueError):
        next_incident_status("RESOLVED", "resolve")
