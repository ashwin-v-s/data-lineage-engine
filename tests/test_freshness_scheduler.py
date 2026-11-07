"""Offline tests for the deliberately blocked M2/M1 scheduler boundary."""
from __future__ import annotations

import pytest

from backend.app.services.freshness_scheduler import (
    BlockedFreshnessScheduler,
    FreshnessSchedule,
    SCHEDULER_BLOCK_REASON,
    scheduler_status,
)
from backend.app.api.routes.governance import _serialize_sla


def test_nonmanual_cadence_is_explicitly_blocked_until_runtime_approval():
    assert scheduler_status("manual") == "MANUAL"
    assert scheduler_status("15m") == "BLOCKED"
    with pytest.raises(RuntimeError, match="M2/M1"):
        BlockedFreshnessScheduler().configure(FreshnessSchedule("workspace", "dataset", "15m", False))
    assert SCHEDULER_BLOCK_REASON


def test_sla_api_serialization_never_claims_nonmanual_cadence_is_running():
    row = {
        "id": "sla-1", "dataset_id": "dataset-1", "warn_after_minutes": 60,
        "error_after_minutes": 75, "stale_after_minutes": 120,
        "signal": "openlineage_run", "evaluation_schedule": "hourly",
        "paused": False, "created_at": "now",
    }
    assert _serialize_sla(row)["scheduler_status"] == "BLOCKED"
