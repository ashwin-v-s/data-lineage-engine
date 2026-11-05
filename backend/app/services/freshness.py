"""
backend/app/services/freshness.py
─────────────────────────────────
Pure, dependency-free freshness evaluator and incident-workflow helpers.

This module performs **no** I/O: it takes stored facts (the last observed source
activity time and the configured thresholds) and returns a verdict.  The
evidence-first rule lives here: a dataset is never reported ``LATE`` or
``STALE`` without evidence.  When the SLA or the source activity is missing the
verdict is ``UNKNOWN`` — Kairos does not assume staleness.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

__all__ = [
    "FRESHNESS_STATES",
    "FreshnessVerdict",
    "evaluate_freshness",
    "incident_dedupe_key",
    "incident_severity_for_state",
    "next_incident_status",
]

FRESHNESS_STATES: tuple[str, ...] = ("HEALTHY", "AT_RISK", "LATE", "STALE", "UNKNOWN")

_REASON_NO_SLA = "No freshness SLA is configured."
_REASON_NO_ACTIVITY = (
    "No observed source activity; Kairos does not assume staleness without evidence."
)


@dataclass(frozen=True)
class FreshnessVerdict:
    """The outcome of one freshness evaluation."""

    state: str
    age_minutes: int | None
    threshold_minutes: int | None
    reason: str


def _as_utc(moment: datetime) -> datetime:
    """Return ``moment`` as an aware UTC datetime.

    Aware datetimes are converted to UTC; naive datetimes are treated as UTC.
    This never raises, so a caller can mix aware and naive values safely.
    """
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def evaluate_freshness(
    *,
    last_source_activity_at: datetime | None,
    now: datetime,
    warn_after_minutes: int | None,
    error_after_minutes: int | None,
    stale_after_minutes: int | None = None,
) -> FreshnessVerdict:
    """Evaluate the freshness state for one dataset.

    Rule order (the contract):

    1. Missing warn/error thresholds → ``UNKNOWN``.
    2. No observed source activity → ``UNKNOWN`` (never ``LATE``).
    3. Otherwise compute the age and compare it against the thresholds,
       highest first: stale, then error, then warn, otherwise ``HEALTHY``.
    """
    if warn_after_minutes is None or error_after_minutes is None:
        return FreshnessVerdict("UNKNOWN", None, None, _REASON_NO_SLA)
    if last_source_activity_at is None:
        return FreshnessVerdict("UNKNOWN", None, None, _REASON_NO_ACTIVITY)

    age_minutes = max(0, math.floor((_as_utc(now) - _as_utc(last_source_activity_at)).total_seconds() / 60))
    stale_limit = stale_after_minutes if stale_after_minutes is not None else error_after_minutes * 3

    if age_minutes >= stale_limit:
        return FreshnessVerdict(
            "STALE",
            age_minutes,
            stale_limit,
            f"Source activity is {age_minutes} minutes old; the {stale_limit}-minute stale threshold was reached.",
        )
    if age_minutes >= error_after_minutes:
        return FreshnessVerdict(
            "LATE",
            age_minutes,
            error_after_minutes,
            f"Source activity is {age_minutes} minutes old; the {error_after_minutes}-minute error threshold was reached.",
        )
    if age_minutes >= warn_after_minutes:
        return FreshnessVerdict(
            "AT_RISK",
            age_minutes,
            warn_after_minutes,
            f"Source activity is {age_minutes} minutes old; the {warn_after_minutes}-minute warning threshold was reached.",
        )
    return FreshnessVerdict(
        "HEALTHY",
        age_minutes,
        warn_after_minutes,
        f"Source activity is {age_minutes} minutes old; within the {warn_after_minutes}-minute warning threshold.",
    )


def incident_dedupe_key(dataset_id: str, *, kind: str = "freshness") -> str:
    """Return the stable per-breach dedupe key for a dataset."""
    return f"{kind}:{dataset_id}"


def incident_severity_for_state(state: str) -> str:
    """Map a freshness state to an incident severity."""
    if state == "STALE":
        return "HIGH"
    if state == "LATE":
        return "MEDIUM"
    return "LOW"


# Allowed incident status transitions.  A missing action (or a terminal status)
# is an illegal transition and raises ValueError.
_TRANSITIONS: dict[str, dict[str, str]] = {
    "DETECTED": {
        "acknowledge": "ACKNOWLEDGED",
        "investigate": "INVESTIGATING",
        "resolve": "RESOLVED",
    },
    "ACKNOWLEDGED": {
        "investigate": "INVESTIGATING",
        "resolve": "RESOLVED",
    },
    "INVESTIGATING": {
        "resolve": "RESOLVED",
    },
    "RESOLVED": {},
}


def next_incident_status(current: str, action: str) -> str:
    """Return the status after applying ``action`` to an incident in ``current``.

    Raises :class:`ValueError` for an unknown status or an illegal transition.
    """
    allowed = _TRANSITIONS.get(current)
    if allowed is None:
        raise ValueError(f"Unknown incident status '{current}'.")
    if action not in allowed:
        raise ValueError(f"Cannot '{action}' an incident in status '{current}'.")
    return allowed[action]
