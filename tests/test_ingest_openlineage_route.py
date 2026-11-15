"""HTTP contract tests for POST /api/v1/ingest/openlineage (+ /preview).

The route is exercised end to end against an in-memory cursor, so these tests
cover validation, batching, idempotency and the write path together:

  R1  A COMPLETE event with inputs + outputs is accepted and writes evidence.
  R2  Replaying the same payload is idempotent.
  R3  Non-COMPLETE events store the run but produce zero evidence.
  R4  A missing run.runId is skipped.
  R5  A missing job.name is skipped.
  R6  A batch of >100 events returns 413 BATCH_TOO_LARGE.
  R7  An empty batch returns 200 with zero counters.
  R8  Invalid JSON returns 400 INVALID_JSON.
  R9  A body that is neither an event nor a batch returns 400 INVALID_PAYLOAD.
  R10 Multiple inputs and outputs create evidence per pair but no edges.
  R11 A COMPLETE event with no inputs/outputs produces no evidence.
  R12 The columnLineage facet is noted in diagnostics and does not block.
  R13 The preview endpoint normalizes without writing.
  R14 An unauthenticated producer is rejected.
"""
from __future__ import annotations

import json
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

# psycopg2 stub — only when the driver is genuinely absent, so an installed
# psycopg2 (with Json / execute_values) is never shadowed by a partial fake.
try:
    import psycopg2  # noqa: F401
    import psycopg2.extras  # noqa: F401
    import psycopg2.pool  # noqa: F401
except ImportError:  # pragma: no cover - only on hosts without the driver
    _psycopg2_stub = ModuleType("psycopg2")
    _psycopg2_stub.connect = MagicMock()
    _psycopg2_stub.OperationalError = Exception
    _psycopg2_stub.Error = Exception

    _extras = ModuleType("psycopg2.extras")
    _extras.RealDictCursor = dict
    _extras.Json = lambda value: value
    _extras.execute_values = MagicMock()

    _pool = ModuleType("psycopg2.pool")
    _pool.ThreadedConnectionPool = MagicMock()

    sys.modules["psycopg2"] = _psycopg2_stub
    sys.modules["psycopg2.extras"] = _extras
    sys.modules["psycopg2.pool"] = _pool

from fastapi.testclient import TestClient  # noqa: E402 — after stub

from backend.app.auth import require_user  # noqa: E402
from backend.app.main import app  # noqa: E402
from tests.openlineage_fake_db import FakeCursor, make_get_conn  # noqa: E402

client = TestClient(app)


def _complete_event(
    run_id: str = "run-001",
    job: str = "kairos.test_job",
    inputs: list | None = None,
    outputs: list | None = None,
) -> dict:
    return {
        "eventType": "COMPLETE",
        "eventTime": "2026-10-01T08:00:00Z",
        "run": {"runId": run_id},
        "job": {"namespace": "kairos://test", "name": job},
        "inputs": inputs if inputs is not None else [{"namespace": "pg://db", "name": "employees"}],
        "outputs": outputs if outputs is not None else [{"namespace": "pg://db", "name": "out_adjusted"}],
        "producer": "kairos-test",
    }


def _start_event(run_id: str = "run-001") -> dict:
    return {
        "eventType": "START",
        "eventTime": "2026-10-01T07:59:00Z",
        "run": {"runId": run_id},
        "job": {"namespace": "kairos://test", "name": "kairos.test_job"},
        "producer": "kairos-test",
    }


@pytest.fixture(autouse=True)
def authenticated_workspace():
    """Every request runs as a verified user with a provisioned workspace."""
    app.dependency_overrides[require_user] = lambda: {
        "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "email": "demo@example.com",
    }
    yield
    app.dependency_overrides.pop(require_user, None)


@pytest.fixture
def cursor():
    return FakeCursor()


def _post(cursor: FakeCursor, path: str, payload):
    with patch(
        "backend.app.api.routes.ingest.get_conn",
        side_effect=make_get_conn(cursor),
    ):
        return client.post(path, json=payload)


# ---------------------------------------------------------------------------
# R1
# ---------------------------------------------------------------------------

def test_r1_complete_event_accepted(cursor):
    resp = _post(cursor, "/api/v1/ingest/openlineage", _complete_event())

    assert resp.status_code == 200
    data = resp.json()
    assert data["accepted"] == 1
    assert data["duplicate"] == 0
    assert data["skipped"] == 0
    assert data["evidence_created"] == 1
    assert data["edges_created"] == 1
    assert data["runs_written"] == 1
    assert len(cursor.raw_events) == 1
    assert len(cursor.evidence) == 1
    assert len(cursor.edges) == 1


# ---------------------------------------------------------------------------
# R2
# ---------------------------------------------------------------------------

def test_r2_duplicate_event_is_idempotent(cursor):
    event = _complete_event()

    resp1 = _post(cursor, "/api/v1/ingest/openlineage", event)
    resp2 = _post(cursor, "/api/v1/ingest/openlineage", event)

    assert resp1.json()["accepted"] == 1
    assert resp1.json()["duplicate"] == 0
    assert resp2.json()["accepted"] == 0
    assert resp2.json()["duplicate"] == 1
    assert resp2.json()["evidence_created"] == 0
    assert len(cursor.evidence) == 1
    assert len(cursor.edges) == 1


# ---------------------------------------------------------------------------
# R3
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("event_type", ["START", "FAIL", "ABORT", "RUNNING"])
def test_r3_non_complete_event_produces_no_evidence(cursor, event_type):
    event = {
        "eventType": event_type,
        "eventTime": "2026-10-01T08:00:00Z",
        "run": {"runId": "run-nc"},
        "job": {"name": "kairos.test_job"},
        "producer": "kairos-test",
    }
    resp = _post(cursor, "/api/v1/ingest/openlineage", event)

    assert resp.status_code == 200
    data = resp.json()
    assert data["evidence_created"] == 0
    assert data["edges_created"] == 0
    assert data["accepted"] == 1
    assert any(event_type in message or event_type.lower() in message for message in data["diagnostics"])


# ---------------------------------------------------------------------------
# R4 / R5
# ---------------------------------------------------------------------------

def test_r4_missing_run_id_is_skipped(cursor):
    event = {"eventType": "COMPLETE", "eventTime": "2026-10-01T08:00:00Z",
             "run": {}, "job": {"name": "kairos.test_job"}}

    resp = _post(cursor, "/api/v1/ingest/openlineage", event)

    assert resp.status_code == 200
    data = resp.json()
    assert data["accepted"] == 0
    assert data["skipped"] == 1
    assert data["evidence_created"] == 0
    assert cursor.raw_events == {}


def test_r5_missing_job_name_is_skipped(cursor):
    event = {"eventType": "COMPLETE", "eventTime": "2026-10-01T08:00:00Z",
             "run": {"runId": "run-001"}, "job": {}}

    resp = _post(cursor, "/api/v1/ingest/openlineage", event)

    assert resp.status_code == 200
    assert resp.json()["skipped"] == 1
    assert resp.json()["evidence_created"] == 0


# ---------------------------------------------------------------------------
# R6 / R7
# ---------------------------------------------------------------------------

def test_r6_batch_too_large_returns_413(cursor):
    batch = {"events": [_complete_event(run_id=f"run-{i}") for i in range(101)]}

    resp = _post(cursor, "/api/v1/ingest/openlineage", batch)

    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "BATCH_TOO_LARGE"
    assert cursor.executed == []


def test_r7_empty_batch_returns_200(cursor):
    resp = _post(cursor, "/api/v1/ingest/openlineage", {"events": []})

    assert resp.status_code == 200
    assert resp.json()["accepted"] == 0
    assert cursor.count_sql("insert into evidence") == 0


# ---------------------------------------------------------------------------
# R8 / R9
# ---------------------------------------------------------------------------

def test_r8_invalid_json_returns_400(cursor):
    with patch(
        "backend.app.api.routes.ingest.get_conn",
        side_effect=make_get_conn(cursor),
    ):
        resp = client.post(
            "/api/v1/ingest/openlineage",
            content=b"not json at all }{",
            headers={"Content-Type": "application/json"},
        )

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_JSON"


def test_r9_body_without_eventtype_or_events_returns_400(cursor):
    resp = _post(cursor, "/api/v1/ingest/openlineage", {"foo": "bar"})

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_PAYLOAD"
    assert cursor.executed == []


# ---------------------------------------------------------------------------
# R10
# ---------------------------------------------------------------------------

def test_r10_no_cartesian_product_lineage_edges_created(cursor):
    event = _complete_event(
        inputs=[
            {"namespace": "pg://db", "name": "customers"},
            {"namespace": "pg://db", "name": "orders"},
        ],
        outputs=[
            {"namespace": "pg://db", "name": "out_summary"},
            {"namespace": "pg://db", "name": "out_report"},
        ],
    )

    resp = _post(cursor, "/api/v1/ingest/openlineage", event)

    assert resp.status_code == 200
    data = resp.json()
    assert data["evidence_created"] == 4
    assert data["edges_created"] == 0
    assert cursor.count_sql("insert into lineage_edge") == 0
    assert any("multiple_outputs" in message for message in data["diagnostics"])


# ---------------------------------------------------------------------------
# R11 / R12
# ---------------------------------------------------------------------------

def test_r11_complete_with_no_inputs_produces_no_evidence(cursor):
    event = {"eventType": "COMPLETE", "eventTime": "2026-10-01T08:00:00Z",
             "run": {"runId": "run-empty"}, "job": {"name": "kairos.empty_job"},
             "inputs": [], "outputs": []}

    resp = _post(cursor, "/api/v1/ingest/openlineage", event)

    assert resp.status_code == 200
    data = resp.json()
    assert data["evidence_created"] == 0
    assert data["accepted"] == 1


def test_r12_column_lineage_facet_noted_in_diagnostics(cursor):
    event = _complete_event()
    event["outputs"][0]["facets"] = {
        "columnLineage": {"_producer": "test", "fields": {"salary": {"inputFields": []}}},
    }

    resp = _post(cursor, "/api/v1/ingest/openlineage", event)

    assert resp.status_code == 200
    data = resp.json()
    assert data["accepted"] == 1
    assert any("columnLineage" in message for message in data["diagnostics"])


# ---------------------------------------------------------------------------
# R13 — preview writes nothing
# ---------------------------------------------------------------------------

def test_r13_preview_returns_normalized_event_without_writes(cursor):
    resp = _post(
        cursor,
        "/api/v1/ingest/openlineage/preview",
        _complete_event(inputs=[{"namespace": "pg://db", "name": "analytics.orders"}]),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["writes"] == 0
    assert data["count"] == 1
    assert data["valid_count"] == 1
    event = data["events"][0]
    assert event["eventType"] == "COMPLETE"
    assert event["runId"] == "run-001"
    assert event["job"]["name"] == "kairos.test_job"
    assert event["producer"] == "kairos-test"
    assert event["inputs"][0]["table"] == "orders"
    assert event["outputs"][0]["table"] == "out_adjusted"
    assert cursor.executed == []


def test_preview_of_batch_reports_invalid_events(cursor):
    resp = _post(
        cursor,
        "/api/v1/ingest/openlineage/preview",
        {"events": [_complete_event(run_id="run-a"), {"eventType": "COMPLETE"}]},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2
    assert data["valid_count"] == 1
    assert any("run.runId" in warning for warning in data["warnings"])


# ---------------------------------------------------------------------------
# R14 — authentication is required
# ---------------------------------------------------------------------------

def test_r14_unauthenticated_producer_is_rejected(cursor):
    app.dependency_overrides.pop(require_user, None)
    try:
        with patch(
            "backend.app.api.routes.ingest.get_conn",
            side_effect=make_get_conn(cursor),
        ):
            resp = client.post("/api/v1/ingest/openlineage", json=_complete_event())
    finally:
        app.dependency_overrides[require_user] = lambda: {"id": "restored"}

    assert resp.status_code == 401
    assert cursor.executed == []


# ---------------------------------------------------------------------------
# Batch + run status
# ---------------------------------------------------------------------------

def test_batch_two_events_both_accepted(cursor):
    batch = {"events": [_complete_event(run_id="run-A"), _complete_event(run_id="run-B")]}

    resp = _post(cursor, "/api/v1/ingest/openlineage", batch)

    assert resp.status_code == 200
    data = resp.json()
    assert data["accepted"] == 2
    assert data["duplicate"] == 0
    assert data["evidence_created"] == 2
    assert set(cursor.runs) == {"run-A", "run-B"}
    assert {run["status"] for run in cursor.runs.values()} == {"completed"}


def test_absence_never_creates_negative_evidence(cursor):
    _post(cursor, "/api/v1/ingest/openlineage", {"events": []})

    assert cursor.count_sql("insert into evidence") == 0
    assert cursor.count_sql("insert into raw_event") == 0


def test_storage_failure_returns_503(cursor):
    def _broken():
        raise RuntimeError("pool exhausted")

    with patch("backend.app.api.routes.ingest.get_conn", side_effect=_broken):
        resp = client.post("/api/v1/ingest/openlineage", json=_complete_event())

    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "STORAGE_UNAVAILABLE"


def test_response_shape_is_stable(cursor):
    data = _post(cursor, "/api/v1/ingest/openlineage", _complete_event()).json()

    assert set(data) >= {
        "accepted", "duplicate", "skipped", "evidence_created",
        "edges_created", "runs_written", "diagnostics",
    }
    json.dumps(data)  # must be JSON serializable
