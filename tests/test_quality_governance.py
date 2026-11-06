"""Database-free tests for the metadata-only quality assertion evaluator."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.app.api.routes.quality import AssertionInput, _result_for_assertion, create_assertion


class MemoryCursor:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.rows = []
        self.queries = []

    def execute(self, _query, _params=()):
        self.queries.append((_query, _params))
        self.rows = next(self.replies)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


def test_completeness_assertion_returns_metadata_field_diagnostics_only():
    cur = MemoryCursor([[{"name": "orders", "source_system": "", "schema_name": "public"}]])
    result = _result_for_assertion(cur, {
        "dataset_id": "dataset-1", "assertion_type": "completeness",
        "definition": {"required_fields": ["name", "source_system", "schema_name"]},
    })
    assert result["status"] == "FAIL"
    assert result["checked_count"] == 3
    assert result["failed_count"] == 1
    assert result["evidence"]["missing_metadata_fields"] == ["source_system"]


def test_freshness_without_runtime_evidence_is_skipped_not_failed():
    cur = MemoryCursor([[]])
    result = _result_for_assertion(cur, {
        "dataset_id": "dataset-1", "assertion_type": "freshness",
        "definition": {"max_age_minutes": 60},
    })
    assert result["status"] == "SKIPPED"
    assert result["evidence"]["state"] == "UNKNOWN"
    sql, params = cur.queries[0]
    assert "JOIN execution_run er ON er.run_id = e.run_id" in sql
    assert "er.status = 'completed'" in sql
    assert "er.completed_at IS NOT NULL" in sql
    assert "ingestion_time" not in sql
    assert params == {"dataset": "dataset-1"}


def test_freshness_uses_only_completed_run_timestamp_and_retains_evidence():
    from datetime import datetime, timedelta, timezone

    completed = datetime.now(timezone.utc) - timedelta(minutes=90)
    cur = MemoryCursor([[{
        "last_activity": completed,
        "evidence_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "run_id": "run-1",
        "evidence_ref": {"kind": "SUCCESSFUL_RUNTIME_EVIDENCE", "run_id": "run-1"},
    }]])
    result = _result_for_assertion(cur, {
        "dataset_id": "dataset-1", "assertion_type": "freshness",
        "definition": {"max_age_minutes": 60},
    })
    assert result["status"] == "FAIL"
    assert result["evidence"]["evidence_id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert result["evidence"]["run_id"] == "run-1"


def test_custom_sql_assertion_is_never_executed():
    result = _result_for_assertion(MemoryCursor([]), {
        "dataset_id": "dataset-1", "assertion_type": "custom_sql", "definition": {"sql": "SELECT 1"},
    })
    assert result["status"] == "SKIPPED"
    assert result["evidence"]["supported"] is False


def test_custom_sql_creation_fails_closed_before_database_access():
    body = AssertionInput.model_validate({
        "dataset_id": "11111111-1111-1111-1111-111111111111", "name": "unsafe",
        "assertion_type": "custom_sql", "definition": {"sql": "SELECT 1"},
    })
    with pytest.raises(HTTPException) as exc:
        create_assertion(body, {"id": "11111111-1111-1111-1111-111111111111"})
    assert exc.value.status_code == 501
