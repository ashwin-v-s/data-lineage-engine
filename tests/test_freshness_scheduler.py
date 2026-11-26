"""Offline tests for the freshness scheduler status and legacy boundary."""
from __future__ import annotations

import pytest

from backend.app.api.routes.governance import _serialize_sla
from backend.app.services.freshness_scheduler import (
    SCHEDULER_BLOCK_REASON,
    BlockedFreshnessScheduler,
    FreshnessSchedule,
    scheduler_status,
)


def test_nonmanual_cadence_is_explicitly_blocked_until_runtime_approval(monkeypatch):
    monkeypatch.delenv("KAIROS_FRESHNESS_SCHEDULE_ENABLED", raising=False)
    assert scheduler_status("manual") == "MANUAL"
    assert scheduler_status("15m") == "BLOCKED"
    with pytest.raises(RuntimeError, match="M2/M1"):
        BlockedFreshnessScheduler().configure(FreshnessSchedule("workspace", "dataset", "15m", False))
    assert SCHEDULER_BLOCK_REASON


def test_sla_api_serialization_never_claims_nonmanual_cadence_is_running(monkeypatch):
    monkeypatch.delenv("KAIROS_FRESHNESS_SCHEDULE_ENABLED", raising=False)
    row = {
        "id": "sla-1", "dataset_id": "dataset-1", "warn_after_minutes": 60,
        "error_after_minutes": 75, "stale_after_minutes": 120,
        "signal": "openlineage_run", "evaluation_schedule": "hourly",
        "paused": False, "created_at": "now",
    }
    assert _serialize_sla(row)["scheduler_status"] == "BLOCKED"


def test_nonmanual_cadence_reports_scheduled_when_runtime_is_enabled(monkeypatch):
    monkeypatch.setenv("KAIROS_FRESHNESS_SCHEDULE_ENABLED", "true")
    assert scheduler_status("hourly") == "SCHEDULED"
