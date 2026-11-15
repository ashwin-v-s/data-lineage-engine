"""Catalog read-model labelling tests.

The canvas, the evidence strip and the Runs page all read this one payload, so
an OpenLineage runtime event must not arrive as UNKNOWN just because no
column-level ``execution_state`` row exists, and a stored ``completed`` run must
not arrive as a status the Runs filter cannot express.
"""
from __future__ import annotations

from fastapi import Response

from backend.app.api.routes import search as search_module


def _evidence_row(evidence_id, evidence_type, execution_state=None):
    return {
        "id": evidence_id,
        "evidence_id": f"ol-{evidence_id}",
        "evidence_type": evidence_type,
        "source_system": "openlineage",
        "run_id": "run_999",
        "granularity": "DATASET",
        "operator": None,
        "coverage": None,
        "diagnostics": None,
        "event_time": None,
        "effective_time": None,
        "source_dataset": "analytics.orders",
        "source_column": None,
        "target_dataset": "analytics.revenue_daily",
        "target_column": None,
        "execution_state": execution_state,
    }


class _Cursor:
    def __init__(self):
        self.query = ""

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, query, params=()):
        self.query = " ".join(query.split())

    def fetchone(self):
        query = self.query
        if "COUNT(*)" in query:
            return {"count": 3}
        return {"count": 0}

    def fetchall(self):
        query = self.query
        if "FROM dataset d" in query:
            return [
                {"id": "asset-orders", "source_system": "postgres", "namespace": "prod",
                 "database_name": "analytics", "schema_name": "public", "name": "orders",
                 "asset_type": "table", "created_at": None, "column_count": 0},
                {"id": "asset-revenue", "source_system": "postgres", "namespace": "prod",
                 "database_name": "analytics", "schema_name": "public", "name": "revenue_daily",
                 "asset_type": "table", "created_at": None, "column_count": 0},
            ]
        if "FROM lineage_edge le" in query:
            return []
        if "FROM execution_run er" in query:
            return [
                {"run_id": "run_999", "status": "completed", "started_at": None,
                 "completed_at": None, "job_name": "new_revenue_job"},
                {"run_id": "run_998", "status": "failed", "started_at": None,
                 "completed_at": None, "job_name": "new_revenue_job"},
                {"run_id": "run_997", "status": "running", "started_at": None,
                 "completed_at": None, "job_name": "new_revenue_job"},
                {"run_id": "run_996", "status": "queued", "started_at": None,
                 "completed_at": None, "job_name": "new_revenue_job"},
            ]
        if "FROM evidence e" in query:
            return [
                _evidence_row("ev-1", "STATIC_DEPENDENCY"),
                _evidence_row("ev-2", "RUNTIME_POSITIVE"),
                _evidence_row("ev-3", "STATIC_DEPENDENCY", execution_state="REFUTED_FOR_RUN"),
                _evidence_row("ev-4", "SOMETHING_ELSE"),
            ]
        return []


class _Connection:
    def __init__(self):
        self.cur = _Cursor()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self, *_, **__):
        return self.cur


def _snapshot(monkeypatch):
    monkeypatch.setattr(search_module, "get_conn", _Connection)
    return search_module.catalog_snapshot(Response(), limit=10, offset=0, user={"id": "user"})


def test_catalog_labels_evidence_by_the_claim_its_own_type_makes(monkeypatch):
    result = _snapshot(monkeypatch)

    states = {row["id"]: row["state"] for row in result["evidence"]}
    assert states == {
        "ev-1": "POSSIBLE",
        "ev-2": "OBSERVED",
        "ev-3": "REFUTED_FOR_RUN",
        "ev-4": "UNKNOWN",
    }


def test_a_reasoning_result_still_wins_over_the_evidence_type_default(monkeypatch):
    result = _snapshot(monkeypatch)

    refuted = next(row for row in result["evidence"] if row["id"] == "ev-3")
    assert refuted["state"] == "REFUTED_FOR_RUN"
    assert refuted["evidence_type"] == "STATIC_DEPENDENCY"


def test_catalog_maps_stored_run_status_to_the_runs_view_vocabulary(monkeypatch):
    result = _snapshot(monkeypatch)

    assert [row["status"] for row in result["runs"]] == [
        "SUCCESS", "FAILED", "RUNNING", "QUEUED",
    ]


def test_openlineage_evidence_is_not_reported_as_unknown(monkeypatch):
    result = _snapshot(monkeypatch)

    observed = next(row for row in result["evidence"] if row["id"] == "ev-2")
    assert observed["state"] == "OBSERVED"
    assert observed["source_name"] == "analytics.orders"
    assert observed["target_name"] == "analytics.revenue_daily"
