"""Service-level tests for OpenLineage normalization and persistence.

These exercise the real service against an in-memory cursor, so the assertions
cover the full write path rather than a mocked return value:

    event -> raw_event -> job -> execution_run -> dataset -> evidence
          -> lineage_edge -> edge_temporal_version
"""
from __future__ import annotations

import pytest

from backend.app.services.openlineage_ingest import (
    canonical_event_type,
    dataset_identity,
    event_identifier,
    ingest_openlineage_events,
    run_status_for,
    summarize_event,
)
from tests.openlineage_fake_db import FakeCursor


def _event(
    *,
    run_id: str = "run_999",
    event_type: str = "COMPLETE",
    inputs: list | None = None,
    outputs: list | None = None,
    event_time: str = "2026-11-01T10:00:00Z",
    event_id: str | None = None,
) -> dict:
    event = {
        "eventType": event_type,
        "eventTime": event_time,
        "run": {"runId": run_id},
        "job": {"namespace": "kairos://demo", "name": "new_revenue_job"},
        "inputs": inputs if inputs is not None else [
            {"namespace": "postgres://db:5432/warehouse", "name": "analytics.orders"}
        ],
        "outputs": outputs if outputs is not None else [
            {"namespace": "postgres://db:5432/warehouse", "name": "analytics.revenue_daily"}
        ],
        "producer": "kairos-test",
    }
    if event_id:
        event["eventId"] = event_id
    return event


def _ingest(cursor: FakeCursor, events: list[dict]) -> dict:
    return ingest_openlineage_events(cursor, events)


def test_complete_event_writes_the_whole_path():
    cursor = FakeCursor()

    result = _ingest(cursor, [_event()])

    assert result["accepted"] == 1
    assert result["duplicate"] == 0
    assert result["skipped"] == 0
    assert result["evidence_created"] == 1
    assert result["edges_created"] == 1
    assert result["runs_written"] == 1

    assert len(cursor.raw_events) == 1
    assert list(cursor.raw_events)[0].startswith("ol:11111111-1111-4111-8111-111111111111:")
    assert cursor.jobs == {("kairos://demo", "new_revenue_job"): "job-1"}
    assert cursor.runs["run_999"]["status"] == "completed"
    assert set(cursor.datasets) == {
        ("analytics", "orders"),
        ("analytics", "revenue_daily"),
    }
    assert len(cursor.evidence) == 1
    assert len(cursor.edges) == 1
    assert cursor.edges[0]["operator"] == "openlineage:dataset_boundary"
    assert len(cursor.temporal) == 1


def test_replaying_the_same_event_writes_nothing_new():
    cursor = FakeCursor()
    event = _event()

    first = _ingest(cursor, [event])
    second = _ingest(cursor, [event])

    assert first["accepted"] == 1
    assert second["accepted"] == 0
    assert second["duplicate"] == 1
    assert second["evidence_created"] == 0
    assert second["edges_created"] == 0
    assert len(cursor.evidence) == 1
    assert len(cursor.edges) == 1
    assert len(cursor.temporal) == 1


def test_replay_with_a_new_event_id_reuses_the_existing_edge():
    cursor = FakeCursor()

    _ingest(cursor, [_event(event_id="evt-1")])
    second = _ingest(cursor, [_event(event_id="evt-2")])

    assert second["accepted"] == 1
    assert second["evidence_created"] == 0  # same run/source/target evidence id
    assert second["edges_created"] == 0
    assert len(cursor.edges) == 1
    assert len(cursor.temporal) == 1


@pytest.mark.parametrize("event_type", ["START", "RUNNING", "FAIL", "ABORT", "OTHER"])
def test_non_complete_events_store_the_run_but_never_evidence(event_type: str):
    cursor = FakeCursor()

    result = _ingest(cursor, [_event(event_type=event_type)])

    assert result["accepted"] == 1
    assert result["evidence_created"] == 0
    assert result["edges_created"] == 0
    assert result["runs_written"] == 1
    assert len(cursor.raw_events) == 1
    assert any(event_type in message for message in result["diagnostics"])


def test_late_start_does_not_reopen_a_completed_run():
    cursor = FakeCursor()

    _ingest(cursor, [_event(event_id="complete", event_type="COMPLETE")])
    _ingest(cursor, [_event(event_id="start", event_type="START",
                          event_time="2026-11-01T11:00:00Z")])

    assert cursor.runs["run_999"]["status"] == "completed"


def test_one_output_with_two_inputs_creates_one_edge_per_input():
    cursor = FakeCursor()
    event = _event(
        inputs=[
            {"namespace": "postgres://db:5432/warehouse", "name": "analytics.orders"},
            {"namespace": "postgres://db:5432/warehouse", "name": "analytics.payments"},
        ]
    )

    result = _ingest(cursor, [event])

    assert result["evidence_created"] == 2
    assert result["edges_created"] == 2
    assert len(cursor.edges) == 2
    assert len({edge["target"] for edge in cursor.edges}) == 1
    assert len({edge["source"] for edge in cursor.edges}) == 2


def test_multiple_outputs_never_create_pairwise_edges():
    cursor = FakeCursor()
    event = _event(
        inputs=[
            {"namespace": "postgres://db:5432/warehouse", "name": "analytics.orders"},
            {"namespace": "postgres://db:5432/warehouse", "name": "analytics.payments"},
        ],
        outputs=[
            {"namespace": "postgres://db:5432/warehouse", "name": "analytics.revenue_daily"},
            {"namespace": "postgres://db:5432/warehouse", "name": "analytics.revenue_weekly"},
        ],
    )

    result = _ingest(cursor, [event])

    assert result["evidence_created"] == 4
    assert result["edges_created"] == 0
    assert cursor.edges == []
    assert cursor.count_sql("insert into lineage_edge") == 0
    assert any("multiple_outputs" in message for message in result["diagnostics"])


def test_existing_catalog_asset_is_reused_instead_of_duplicated():
    cursor = FakeCursor()
    cursor.datasets[("analytics", "orders")] = "existing-orders"

    result = _ingest(cursor, [_event()])

    assert result["evidence_created"] == 1
    # Only the unseen output dataset is inserted.
    assert cursor.count_sql("insert into dataset") == 1
    assert cursor.datasets[("analytics", "orders")] == "existing-orders"


def test_complete_event_without_inputs_or_outputs_writes_no_evidence():
    cursor = FakeCursor()

    result = _ingest(cursor, [_event(inputs=[], outputs=[])])

    assert result["accepted"] == 1
    assert result["evidence_created"] == 0
    assert result["edges_created"] == 0


def test_missing_run_id_is_skipped_before_any_write():
    cursor = FakeCursor()
    event = _event()
    event["run"] = {}

    result = _ingest(cursor, [event])

    assert result["skipped"] == 1
    assert result["accepted"] == 0
    assert cursor.executed == []


def test_no_event_time_still_stores_evidence():
    cursor = FakeCursor()
    event = _event()
    event.pop("eventTime")

    result = _ingest(cursor, [event])

    assert result["accepted"] == 1
    assert result["evidence_created"] == 1


def test_summarize_event_reports_batch_preview_fields():
    summary = summarize_event(_event())

    assert summary["valid"] is True
    assert summary["eventType"] == "COMPLETE"
    assert summary["producer"] == "kairos-test"
    assert summary["runId"] == "run_999"
    assert summary["job"] == {"namespace": "kairos://demo", "name": "new_revenue_job"}
    assert summary["inputs"][0] == {
        "namespace": "postgres://db:5432/warehouse",
        "name": "analytics.orders",
        "schema": "analytics",
        "table": "orders",
    }
    assert summary["warnings"] == []


def test_summarize_event_flags_invalid_input():
    summary = summarize_event({"eventType": "COMPLETE", "run": {}, "job": {}})

    assert summary["valid"] is False
    assert any("run.runId" in warning for warning in summary["warnings"])
    assert any("job.name" in warning for warning in summary["warnings"])
    assert any("eventTime" in warning for warning in summary["warnings"])


def test_event_type_and_status_mapping():
    assert canonical_event_type("complete") == ("COMPLETE", [])
    assert canonical_event_type("") == ("OTHER", ["missing_event_type"])
    assert canonical_event_type("BOGUS") == ("OTHER", ["unknown_event_type:BOGUS"])
    assert run_status_for("COMPLETE") == "completed"
    assert run_status_for("FAIL") == "failed"
    assert run_status_for("START") == "running"


def test_dataset_identity_parsing():
    assert dataset_identity("postgres://db:5432/warehouse", "analytics.orders") == {
        "database_name": "warehouse", "schema_name": "analytics", "name": "orders",
    }
    assert dataset_identity("pg", "warehouse.analytics.orders") == {
        "database_name": "warehouse", "schema_name": "analytics", "name": "orders",
    }
    assert dataset_identity("pg", "orders") == {
        "database_name": "pg", "schema_name": "", "name": "orders",
    }


def test_event_identifier_prefers_producer_id_then_hash():
    assert event_identifier({"eventId": "evt-1"}) == "evt-1"
    hashed = event_identifier({"job": {"name": "x"}})
    assert len(hashed) == 64
