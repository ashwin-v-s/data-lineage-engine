"""Offline contract tests for governance validation and incident transitions.

Tests call the route functions with an in-memory SQL double. They never create
a FastAPI client or connect to any database.
"""
from __future__ import annotations

from contextlib import contextmanager

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from backend.app.api.routes import governance
from backend.app.api.routes.governance import IncidentResolution, SlaInput
from backend.app.services.freshness import next_incident_status

_USER = {"id": "11111111-1111-1111-1111-111111111111"}

_SLA = {
    "asset_id": "orders",
    "warn_after_minutes": 60,
    "error_after_minutes": 120,
    "signal": "openlineage_run",
}


def test_sla_rejects_error_not_greater_than_warn():
    payload = {**_SLA, "warn_after_minutes": 120, "error_after_minutes": 60}
    with pytest.raises(ValueError):
        SlaInput.model_validate(payload)


def test_sla_rejects_equal_warn_and_error():
    payload = {**_SLA, "warn_after_minutes": 60, "error_after_minutes": 60}
    with pytest.raises(ValueError):
        SlaInput.model_validate(payload)


def test_sla_rejects_zero_warn_after_minutes():
    payload = {**_SLA, "warn_after_minutes": 0}
    with pytest.raises(ValueError):
        SlaInput.model_validate(payload)


def test_sla_rejects_unknown_field():
    payload = {**_SLA, "unexpected_field": "boom"}
    with pytest.raises(ValueError):
        SlaInput.model_validate(payload)


def test_next_incident_status_rejects_illegal_transition():
    with pytest.raises(ValueError):
        next_incident_status("RESOLVED", "resolve")


class _MemoryCursor:
    """Small in-memory SQL double for the authenticated incident route test."""

    def __init__(self, state):
        self.state = state
        self._one = None
        self._many = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=()):
        sql = " ".join(query.split())
        self._one = None
        self._many = []

        if "to_regclass" in sql:
            self._one = {"relation": params[0]}
        elif "SELECT id::text AS id, status FROM incident" in sql:
            self._one = {"id": self.state["id"], "status": self.state["status"]}
        elif sql.startswith("UPDATE incident SET status"):
            self.state["status"] = params[0]
        elif "INSERT INTO incident_event" in sql:
            self.state["events"].append({
                "id": f"event-{len(self.state['events']) + 1}",
                "event_type": params[1],
                "actor_user_id": params[2],
                "detail": params[3].adapted,
                "created_at": "2026-11-03T12:00:00Z",
            })
        elif "FROM incident i JOIN dataset d" in sql:
            self._one = {
                "id": self.state["id"],
                "dataset_id": self.state["dataset_id"],
                "dataset_name": "orders",
                "title": "Freshness breach",
                "severity": "MEDIUM",
                "status": self.state["status"],
                "dedupe_key": "freshness:orders",
                "opened_at": "2026-11-03T11:00:00Z",
                "acknowledged_at": None,
                "resolved_at": None,
                "owner_user_id": _USER["id"],
                "detail": {"evidence_id": "evidence-1"},
            }
        elif "FROM incident_event ev" in sql:
            self._many = list(self.state["events"])
        elif "FROM incident WHERE dataset_id=" in sql:
            self._many = []
        else:
            raise AssertionError(f"Unexpected SQL in offline test double: {sql}")

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._many


class _MemoryConnection:
    def __init__(self, state):
        self.state = state

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def cursor(self, **_kwargs):
        return _MemoryCursor(self.state)


@pytest.fixture
def incident_store(monkeypatch):
    state = {
        "id": "22222222-2222-2222-2222-222222222222",
        "dataset_id": "33333333-3333-3333-3333-333333333333",
        "status": "DETECTED",
        "events": [],
    }

    @contextmanager
    def fake_get_conn():
        yield _MemoryConnection(state)

    monkeypatch.setattr(governance, "get_conn", fake_get_conn)
    return state


def test_incident_route_functions_acknowledge_and_resolve_with_timeline(incident_store):
    incident_id = __import__("uuid").UUID(incident_store["id"])

    acknowledged = governance.acknowledge_incident(incident_id, dict(_USER))
    assert acknowledged["status"] == "ACKNOWLEDGED"

    resolved = governance.resolve_incident(
        incident_id,
        IncidentResolution(reason="Source data was refreshed", action_taken="Replayed the failed source job"),
        dict(_USER),
    )
    assert resolved["status"] == "RESOLVED"
    assert [event["event_type"] for event in resolved["events"]] == ["ACKNOWLEDGED", "RESOLVED"]
    assert incident_store["status"] == "RESOLVED"


# ---------------------------------------------------------------------------
# Regression: incident routes must 503 cleanly when migration 0011 is absent.
# The sentinel is freshness_confirmation: _require_governance() unconditionally
# adds it to every call-site's table list, so if it is missing the route raises
# HTTP 503 before any SELECT that would hit a missing column like resolution_detail.
# ---------------------------------------------------------------------------

class _MigrationAbsentCursor:
    """SQL double that simulates 0009 applied but 0011 not yet applied.

    to_regclass returns None for freshness_confirmation (the 0011 sentinel) and
    a non-null relation string for every 0009 table (incident, etc.).
    This exercises _require_governance() without any real database.
    """

    def __init__(self):
        self._one = None
        self._many = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=()):
        self._one = None
        self._many = []
        if "to_regclass" in query:
            # The first (and only) param is the table name string, e.g. 'public.freshness_confirmation'
            table_arg = params[0] if params else ""
            if "freshness_confirmation" in str(table_arg):
                self._one = {"relation": None}  # 0011 sentinel is absent
            else:
                self._one = {"relation": table_arg}  # 0009 tables exist
        else:
            raise AssertionError(
                f"_MigrationAbsentCursor should not reach SQL beyond to_regclass: {query!r}"
            )

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._many


class _MigrationAbsentConnection:
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def cursor(self, **_kwargs):
        return _MigrationAbsentCursor()


@pytest.fixture
def migration_absent(monkeypatch):
    """Patch get_conn so the 0011 sentinel table (freshness_confirmation) is absent."""

    @contextmanager
    def fake_get_conn():
        yield _MigrationAbsentConnection()

    monkeypatch.setattr(governance, "get_conn", fake_get_conn)


def test_list_incidents_503_when_m4_migration_not_applied(migration_absent):
    """list_incidents must return HTTP 503 before touching resolution_detail."""
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        governance.list_incidents(status=None, user=dict(_USER))
    assert exc.value.status_code == 503
    assert "freshness_confirmation" in exc.value.detail
    assert "0011" in exc.value.detail


def test_get_incident_503_when_m4_migration_not_applied(migration_absent):
    """get_incident must return HTTP 503 before touching resolution_detail."""
    import uuid
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        governance.get_incident(uuid.UUID("22222222-2222-2222-2222-222222222222"), dict(_USER))
    assert exc.value.status_code == 503
    assert "freshness_confirmation" in exc.value.detail
    assert "0011" in exc.value.detail
