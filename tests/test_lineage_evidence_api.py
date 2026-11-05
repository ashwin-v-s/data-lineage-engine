"""Offline request tests for the lineage edge evidence inspector API."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from fastapi import HTTPException

from backend.app.api.routes import lineage as lineage_module


class _Cursor:
    def __init__(self):
        self.states = ["UNKNOWN"]
        self.run_id = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, *_args, **_kwargs):
        return None

    def fetchall(self):
        now = datetime(2026, 11, 5, tzinfo=timezone.utc)
        return [{
            "edge_id": "11111111-1111-4111-8111-111111111111",
            "granularity": "DATASET",
            "operator_fingerprint": "declared_dependency",
            "evidence_row_id": "22222222-2222-4222-8222-222222222222",
            "evidence_id": "fixture-evidence-1",
            "evidence_type": "STATIC_DEPENDENCY",
            "source_system": "dbt",
            "run_id": self.run_id,
            "coverage": None,
            "parser_status": "SUPPORTED",
            "operator": "declared_dependency",
            "diagnostics": {"explanation": "Declared by manifest", "api_key": "should-redact"},
            "event_time": None,
            "effective_time": None,
            "ingestion_time": now,
            "source_dataset_id": "33333333-3333-4333-8333-333333333333",
            "target_dataset_id": "44444444-4444-4444-8444-444444444444",
            "source_column_id": None,
            "target_column_id": None,
            "source_dataset": "orders",
            "source_column": None,
            "target_dataset": "orders_model",
            "target_column": None,
            "valid_from": now,
            "valid_to": None,
            "effective_time_status": "UNKNOWN",
            "recorded_from": now,
            "recorded_to": None,
            "raw_payload": {"provenance": {"adapter": "kairos.dbt", "adapter_version": "1"},
                            "token": "should-redact", "nodes": ["model"]},
            "state": "UNKNOWN",
            "execution_states": self.states,
        }]


class _Connection:
    def __init__(self):
        self.cursor_instance = _Cursor()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self, *_, **__):
        return self.cursor_instance


@pytest.fixture
def invoke(monkeypatch):
    connection = _Connection()
    monkeypatch.setattr(lineage_module, "get_conn", lambda: connection)
    def call(edge_id):
        return lineage_module.edge_evidence(
        edge_id, user={"id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"}
        )
    call.set_states = lambda values: setattr(connection.cursor_instance, "states", values)
    call.set_run_id = lambda value: setattr(connection.cursor_instance, "run_id", value)
    return call


def test_edge_evidence_returns_strength_times_and_sanitized_provenance(invoke):
    edge_id = "11111111-1111-4111-8111-111111111111"
    body = invoke(edge_id)
    assert body["conflict"] is False
    evidence = body["evidence"][0]
    assert evidence["strength"] == "Medium"
    assert evidence["state"] == "UNKNOWN"
    assert evidence["valid_time"]["status"] == "UNKNOWN"
    assert evidence["recorded_time"]["from"].startswith("2026-11-05")
    assert evidence["provenance"]["parser"]["adapter"] == "kairos.dbt"
    assert "token" not in evidence["provenance"]["raw"]
    assert "api_key" not in evidence["provenance"]["normalized"]["diagnostics"]


def test_edge_evidence_rejects_malformed_edge_id_without_database_access(invoke):
    with pytest.raises(HTTPException) as error:
        invoke("not-a-uuid")
    assert error.value.status_code == 404


def test_conflicting_run_states_are_exposed_for_review(invoke):
    invoke.set_states(["OBSERVED", "REFUTED_FOR_RUN"])
    invoke.set_run_id("run-1")
    body = invoke("11111111-1111-4111-8111-111111111111")
    assert body["conflict"] is True
    assert body["conflicting_runs"] == ["run-1"]
