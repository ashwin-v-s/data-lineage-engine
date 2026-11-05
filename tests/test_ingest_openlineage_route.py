"""
Tests for POST /api/v1/ingest/openlineage

These tests run OFFLINE — they stub get_conn() so no real database is
needed.  They verify the route's hard behavioural rules:

  R1  A COMPLETE event with inputs + outputs is accepted.
  R2  Replaying the same event payload is idempotent (duplicate=1, no new rows).
  R3  Non-COMPLETE events (START, FAIL, ABORT) are stored but produce
      zero evidence rows — non-terminal events never become evidence.
  R4  An event missing run.runId is skipped entirely.
  R5  An event missing job.name is skipped entirely.
  R6  A batch of >100 events returns 413 BATCH_TOO_LARGE.
  R7  An empty batch returns accepted=0, no error.
  R8  Invalid JSON body returns 400 INVALID_JSON.
  R9  A body that is neither a single event nor a batch dict returns 400.
  R10 No cartesian-product assertion: the route writes one evidence row per
      (input, output) pair — not a separate "lineage edge" between them.
  R11 A COMPLETE event with no inputs or no outputs produces no evidence rows.
  R12 columnLineage facet detection is noted in diagnostics but does not
      block ingestion.

DB stub strategy: patch get_conn() with an in-memory sqlite-like cursor
mock.  We only care about rowcount signals and that the right SQL strings
are called — not the DB itself.

psycopg2 stub: the module is not installed locally; we inject a minimal
stub before importing anything that transitively pulls it in.
"""
from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# psycopg2 stub — must be injected BEFORE importing backend.app.main
# ---------------------------------------------------------------------------
if "psycopg2" not in sys.modules:
    _psycopg2_stub = ModuleType("psycopg2")
    _psycopg2_stub.connect = MagicMock()
    _psycopg2_stub.OperationalError = Exception

    _extras = ModuleType("psycopg2.extras")
    _extras.RealDictCursor = dict

    _pool = ModuleType("psycopg2.pool")
    _pool.ThreadedConnectionPool = MagicMock()

    sys.modules["psycopg2"] = _psycopg2_stub
    sys.modules["psycopg2.extras"] = _extras
    sys.modules["psycopg2.pool"] = _pool

from fastapi.testclient import TestClient  # noqa: E402 — must come after stub

from backend.app.main import app  # noqa: E402

client = TestClient(app)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

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
        "inputs":  inputs  or [{"namespace": "pg://db", "name": "employees"}],
        "outputs": outputs or [{"namespace": "pg://db", "name": "out_adjusted"}],
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


# ---------------------------------------------------------------------------
# Cursor mock:  first INSERT (raw_event) returns rowcount=1 (new row);
#               second INSERT (evidence) returns rowcount=1.
# Duplicate path: first INSERT returns rowcount=0.
# ---------------------------------------------------------------------------

class _MockCursor:
    """Minimal cursor mock with configurable rowcount sequence."""

    def __init__(self, rowcounts: list[int] | None = None):
        self._rowcounts = list(rowcounts or [1, 1, 1, 1, 1, 1, 1])
        self._call_index = 0
        self.rowcount = 1
        self._last_fetchone = {"id": "00000000-0000-0000-0000-000000000001"}

    def execute(self, sql: str, params: Any = None):
        if self._call_index < len(self._rowcounts):
            self.rowcount = self._rowcounts[self._call_index]
        self._call_index += 1

    def fetchone(self):
        return self._last_fetchone

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


class _MockConn:
    def __init__(self, rowcounts: list[int] | None = None):
        self._cursor = _MockCursor(rowcounts)

    def cursor(self, **_):
        return self._cursor

    def commit(self):
        pass

    def rollback(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


@contextmanager
def _mock_get_conn(rowcounts: list[int] | None = None):
    """Context manager that yields a _MockConn."""
    yield _MockConn(rowcounts)


# ---------------------------------------------------------------------------
# R1 — COMPLETE event accepted
# ---------------------------------------------------------------------------

def test_r1_complete_event_accepted():
    event = _complete_event()
    with patch("backend.app.api.routes.ingest.get_conn", side_effect=_mock_get_conn):
        resp = client.post("/api/v1/ingest/openlineage", json=event)
    assert resp.status_code == 200
    data = resp.json()
    assert data["accepted"] == 1
    assert data["duplicate"] == 0
    assert data["skipped"] == 0


# ---------------------------------------------------------------------------
# R2 — Idempotent replay: second POST with identical payload is a duplicate
# ---------------------------------------------------------------------------

def test_r2_duplicate_event_is_idempotent():
    event = _complete_event()
    # The route calls get_conn() once for the DB availability check, then once
    # per event for the actual INSERT.  Call sequence per POST:
    #   call 0: availability check (no-op conn)
    #   call 1: actual event INSERT → rowcount=1 (first POST, new event)
    #
    #   call 2: availability check (no-op conn)
    #   call 3: actual event INSERT → rowcount=0 (second POST, duplicate)

    call_count = {"n": 0}

    @contextmanager
    def _alternating_conn():
        n = call_count["n"]
        call_count["n"] += 1
        if n % 2 == 0:
            # availability check — just needs to not raise
            yield _MockConn([1])
        elif n == 1:
            # first POST's real INSERT: new raw_event
            yield _MockConn([1, 1, 1, 1, 1])
        else:
            # second POST's real INSERT: duplicate
            yield _MockConn([0])

    with patch("backend.app.api.routes.ingest.get_conn", side_effect=_alternating_conn):
        resp1 = client.post("/api/v1/ingest/openlineage", json=event)
        resp2 = client.post("/api/v1/ingest/openlineage", json=event)

    assert resp1.json()["accepted"] == 1
    assert resp1.json()["duplicate"] == 0

    assert resp2.json()["accepted"] == 0
    assert resp2.json()["duplicate"] == 1
    assert resp2.json()["evidence_created"] == 0


# ---------------------------------------------------------------------------
# R3 — Non-COMPLETE events store raw but write zero evidence
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("event_type", ["START", "FAIL", "ABORT", "RUNNING"])
def test_r3_non_complete_event_produces_no_evidence(event_type: str):
    event = {
        "eventType": event_type,
        "eventTime": "2026-10-01T08:00:00Z",
        "run": {"runId": "run-nc"},
        "job": {"name": "kairos.test_job"},
        "producer": "kairos-test",
    }
    with patch("backend.app.api.routes.ingest.get_conn", side_effect=_mock_get_conn):
        resp = client.post("/api/v1/ingest/openlineage", json=event)

    assert resp.status_code == 200
    data = resp.json()
    assert data["evidence_created"] == 0
    assert data["accepted"] == 1  # raw event stored
    # Diagnostic must mention the event type
    assert any(event_type in d for d in data["diagnostics"])


# ---------------------------------------------------------------------------
# R4 — Missing run.runId → skipped
# ---------------------------------------------------------------------------

def test_r4_missing_run_id_is_skipped():
    event = {
        "eventType": "COMPLETE",
        "eventTime": "2026-10-01T08:00:00Z",
        "run": {},
        "job": {"name": "kairos.test_job"},
    }
    with patch("backend.app.api.routes.ingest.get_conn", side_effect=_mock_get_conn):
        resp = client.post("/api/v1/ingest/openlineage", json=event)

    assert resp.status_code == 200
    data = resp.json()
    assert data["accepted"] == 0
    assert data["skipped"] == 1
    assert data["evidence_created"] == 0


# ---------------------------------------------------------------------------
# R5 — Missing job.name → skipped
# ---------------------------------------------------------------------------

def test_r5_missing_job_name_is_skipped():
    event = {
        "eventType": "COMPLETE",
        "eventTime": "2026-10-01T08:00:00Z",
        "run": {"runId": "run-001"},
        "job": {},
    }
    with patch("backend.app.api.routes.ingest.get_conn", side_effect=_mock_get_conn):
        resp = client.post("/api/v1/ingest/openlineage", json=event)

    assert resp.status_code == 200
    data = resp.json()
    assert data["skipped"] == 1
    assert data["evidence_created"] == 0


# ---------------------------------------------------------------------------
# R6 — Batch > 100 → 413
# ---------------------------------------------------------------------------

def test_r6_batch_too_large_returns_413():
    batch = {"events": [_complete_event(run_id=f"run-{i}") for i in range(101)]}
    with patch("backend.app.api.routes.ingest.get_conn", side_effect=_mock_get_conn):
        resp = client.post("/api/v1/ingest/openlineage", json=batch)
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "BATCH_TOO_LARGE"


# ---------------------------------------------------------------------------
# R7 — Empty batch → 200, accepted=0, no error
# ---------------------------------------------------------------------------

def test_r7_empty_batch_returns_200():
    with patch("backend.app.api.routes.ingest.get_conn", side_effect=_mock_get_conn):
        resp = client.post("/api/v1/ingest/openlineage", json={"events": []})
    assert resp.status_code == 200
    assert resp.json()["accepted"] == 0


# ---------------------------------------------------------------------------
# R8 — Invalid JSON → 400
# ---------------------------------------------------------------------------

def test_r8_invalid_json_returns_400():
    resp = client.post(
        "/api/v1/ingest/openlineage",
        content=b"not json at all }{",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_JSON"


# ---------------------------------------------------------------------------
# R9 — Body is neither a single event nor a batch dict → 400
# ---------------------------------------------------------------------------

def test_r9_body_without_eventtype_or_events_returns_400():
    with patch("backend.app.api.routes.ingest.get_conn", side_effect=_mock_get_conn):
        resp = client.post("/api/v1/ingest/openlineage", json={"foo": "bar"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_PAYLOAD"


# ---------------------------------------------------------------------------
# R10 — No cartesian-product lineage edges
#
# A COMPLETE event with 2 inputs and 2 outputs should produce evidence rows
# for each (input, output) pair that was OBSERVED, but the route must NOT
# create any lineage_edge rows joining inputs to outputs.
#
# We verify this by asserting that no SQL containing "lineage_edge" was
# executed by the cursor during the request.
# ---------------------------------------------------------------------------

def test_r10_no_cartesian_product_lineage_edges_created():
    executed_sql: list[str] = []

    class _TrackingCursor(_MockCursor):
        def execute(self, sql: str, params: Any = None):
            executed_sql.append(sql)
            super().execute(sql, params)

    class _TrackingConn(_MockConn):
        def cursor(self, **_):
            c = _TrackingCursor([1, 1, 1, 1, 1, 1, 1, 1])
            return c

    @contextmanager
    def _tracking_conn():
        yield _TrackingConn()

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
    with patch("backend.app.api.routes.ingest.get_conn", side_effect=_tracking_conn):
        resp = client.post("/api/v1/ingest/openlineage", json=event)

    assert resp.status_code == 200
    # No INSERT INTO lineage_edge should appear in any executed SQL
    for sql in executed_sql:
        assert "lineage_edge" not in sql.lower(), (
            f"Route issued a lineage_edge INSERT — cartesian product forbidden.\n"
            f"Offending SQL: {sql}"
        )


# ---------------------------------------------------------------------------
# R11 — COMPLETE with no inputs/outputs → accepted but no evidence
# ---------------------------------------------------------------------------

def test_r11_complete_with_no_inputs_produces_no_evidence():
    event = {
        "eventType": "COMPLETE",
        "eventTime": "2026-10-01T08:00:00Z",
        "run": {"runId": "run-empty"},
        "job": {"name": "kairos.empty_job"},
        "inputs": [],
        "outputs": [],
    }
    with patch("backend.app.api.routes.ingest.get_conn", side_effect=_mock_get_conn):
        resp = client.post("/api/v1/ingest/openlineage", json=event)

    assert resp.status_code == 200
    data = resp.json()
    assert data["evidence_created"] == 0
    assert data["accepted"] == 1


# ---------------------------------------------------------------------------
# R12 — columnLineage facet noted in diagnostics, does not block ingestion
# ---------------------------------------------------------------------------

def test_r12_column_lineage_facet_noted_in_diagnostics():
    event = _complete_event()
    event["outputs"][0]["facets"] = {
        "columnLineage": {
            "_producer": "test",
            "fields": {"salary": {"inputFields": []}},
        }
    }
    with patch("backend.app.api.routes.ingest.get_conn", side_effect=_mock_get_conn):
        resp = client.post("/api/v1/ingest/openlineage", json=event)

    assert resp.status_code == 200
    data = resp.json()
    assert data["accepted"] == 1
    assert any("columnLineage" in d for d in data["diagnostics"])


# ---------------------------------------------------------------------------
# Batch path — single call with multiple events
# ---------------------------------------------------------------------------

def test_batch_two_events_both_accepted():
    batch = {
        "events": [
            _complete_event(run_id="run-A"),
            _complete_event(run_id="run-B"),
        ]
    }
    call_count = {"n": 0}

    @contextmanager
    def _multi_conn():
        call_count["n"] += 1
        yield _MockConn([1, 1, 1, 1, 1, 1])

    with patch("backend.app.api.routes.ingest.get_conn", side_effect=_multi_conn):
        resp = client.post("/api/v1/ingest/openlineage", json=batch)

    assert resp.status_code == 200
    data = resp.json()
    assert data["accepted"] == 2
    assert data["duplicate"] == 0


# ---------------------------------------------------------------------------
# Absence is not a record — explicit contract test
# ---------------------------------------------------------------------------

def test_absence_never_creates_negative_evidence():
    """
    Sending an empty events list must never write any evidence row.
    This is the machine-testable form of the 'missing events != negatives' rule.
    """
    executed_sql: list[str] = []

    class _TrackingCursor(_MockCursor):
        def execute(self, sql: str, params: Any = None):
            executed_sql.append(sql)
            super().execute(sql, params)

    class _TrackingConn(_MockConn):
        def cursor(self, **_):
            return _TrackingCursor()

    @contextmanager
    def _tracking_conn():
        yield _TrackingConn()

    with patch("backend.app.api.routes.ingest.get_conn", side_effect=_tracking_conn):
        resp = client.post("/api/v1/ingest/openlineage", json={"events": []})

    assert resp.status_code == 200
    # No DB writes should have occurred at all
    evidence_inserts = [s for s in executed_sql if "INSERT INTO evidence" in s]
    assert evidence_inserts == [], (
        "Empty event list produced evidence INSERT — absence must never create evidence."
    )
