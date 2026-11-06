"""Offline, pure tests for the freshness evaluator and incident helpers.

These tests exercise only :mod:`backend.app.services.freshness`; they touch no
database and need no FastAPI app.  The evidence-first contract is asserted
explicitly: an unobserved dataset is ``UNKNOWN`` and never ``LATE``.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.app.services.freshness import (
    FRESHNESS_STATES,
    evaluate_freshness,
    incident_dedupe_key,
    incident_severity_for_state,
    next_incident_status,
)

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _verdict(age_minutes: int, **thresholds):
    return evaluate_freshness(
        last_source_activity_at=NOW - timedelta(minutes=age_minutes),
        now=NOW,
        **thresholds,
    )


def test_states_tuple_is_exactly_the_contract():
    assert FRESHNESS_STATES == ("HEALTHY", "AT_RISK", "LATE", "STALE", "UNKNOWN", "PAUSED")


def test_paused_sla_is_explicit_even_without_activity():
    verdict = evaluate_freshness(last_source_activity_at=None, now=NOW,
                                 warn_after_minutes=None, error_after_minutes=None, paused=True)
    assert verdict.state == "PAUSED"
    assert verdict.age_minutes is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"warn_after_minutes": None, "error_after_minutes": 20},
        {"warn_after_minutes": 10, "error_after_minutes": None},
        {"warn_after_minutes": None, "error_after_minutes": None},
    ],
)
def test_missing_thresholds_yield_unknown(kwargs):
    verdict = evaluate_freshness(last_source_activity_at=NOW, now=NOW, **kwargs)
    assert verdict.state == "UNKNOWN"
    assert verdict.age_minutes is None
    assert verdict.threshold_minutes is None
    assert verdict.reason == "No freshness SLA is configured."


def test_no_source_activity_is_unknown_never_late():
    verdict = evaluate_freshness(
        last_source_activity_at=None,
        now=NOW,
        warn_after_minutes=10,
        error_after_minutes=20,
    )
    assert verdict.state == "UNKNOWN"
    assert verdict.state != "LATE"
    assert verdict.age_minutes is None
    assert verdict.threshold_minutes is None
    assert verdict.reason == (
        "No observed source activity; Kairos does not assume staleness without evidence."
    )


@pytest.mark.parametrize(
    "age,state,threshold",
    [
        (0, "HEALTHY", 10),
        (9, "HEALTHY", 10),
        (10, "HEALTHY", 10),
        (11, "AT_RISK", 10),
        (20, "AT_RISK", 10),
        (21, "LATE", 20),
        (60, "LATE", 20),
        (61, "STALE", 60),
        (120, "STALE", 60),
    ],
)
def test_threshold_boundaries(age, state, threshold):
    verdict = _verdict(age, warn_after_minutes=10, error_after_minutes=20)
    assert verdict.state == state
    assert verdict.age_minutes == age
    assert verdict.threshold_minutes == threshold


@pytest.mark.parametrize(
    "age,state,threshold",
    [
        (29, "LATE", 20),
        (30, "LATE", 20),
        (31, "STALE", 30),
        (45, "STALE", 30),
    ],
)
def test_explicit_stale_threshold(age, state, threshold):
    verdict = _verdict(
        age,
        warn_after_minutes=10,
        error_after_minutes=20,
        stale_after_minutes=30,
    )
    assert verdict.state == state
    assert verdict.age_minutes == age
    assert verdict.threshold_minutes == threshold


def test_naive_and_aware_datetimes_agree():
    aware = evaluate_freshness(
        last_source_activity_at=NOW - timedelta(minutes=25),
        now=NOW,
        warn_after_minutes=10,
        error_after_minutes=20,
    )
    naive_now = NOW.replace(tzinfo=None)
    naive = evaluate_freshness(
        last_source_activity_at=naive_now - timedelta(minutes=25),
        now=naive_now,
        warn_after_minutes=10,
        error_after_minutes=20,
    )
    assert aware.state == naive.state == "LATE"
    assert aware.age_minutes == naive.age_minutes == 25
    assert aware.threshold_minutes == naive.threshold_minutes == 20


def test_mixed_awareness_is_handled():
    naive_last = NOW.replace(tzinfo=None) - timedelta(minutes=5)
    verdict = evaluate_freshness(
        last_source_activity_at=naive_last,
        now=NOW,
        warn_after_minutes=10,
        error_after_minutes=20,
    )
    assert verdict.state == "HEALTHY"
    assert verdict.age_minutes == 5


def test_aware_offsets_are_normalised_to_utc():
    kolkata = timezone(timedelta(hours=5, minutes=30))
    verdict = evaluate_freshness(
        last_source_activity_at=(NOW - timedelta(minutes=30)).astimezone(kolkata),
        now=NOW,
        warn_after_minutes=10,
        error_after_minutes=20,
    )
    assert verdict.state == "LATE"
    assert verdict.age_minutes == 30


def test_future_activity_is_clamped_to_zero():
    verdict = evaluate_freshness(
        last_source_activity_at=NOW + timedelta(minutes=30),
        now=NOW,
        warn_after_minutes=10,
        error_after_minutes=20,
    )
    assert verdict.age_minutes == 0
    assert verdict.state == "HEALTHY"


@pytest.mark.parametrize(
    "state,severity",
    [
        ("STALE", "HIGH"),
        ("LATE", "MEDIUM"),
        ("HEALTHY", "LOW"),
        ("AT_RISK", "LOW"),
        ("UNKNOWN", "LOW"),
    ],
)
def test_incident_severity_for_state(state, severity):
    assert incident_severity_for_state(state) == severity


def test_incident_dedupe_key_default_kind():
    assert incident_dedupe_key("dataset-1") == "freshness:dataset-1"


def test_incident_dedupe_key_custom_kind():
    assert incident_dedupe_key("dataset-1", kind="custom") == "custom:dataset-1"


@pytest.mark.parametrize(
    "current,action,expected",
    [
        ("DETECTED", "acknowledge", "ACKNOWLEDGED"),
        ("DETECTED", "investigate", "INVESTIGATING"),
        ("DETECTED", "resolve", "RESOLVED"),
        ("ACKNOWLEDGED", "investigate", "INVESTIGATING"),
        ("ACKNOWLEDGED", "resolve", "RESOLVED"),
        ("INVESTIGATING", "resolve", "RESOLVED"),
    ],
)
def test_next_incident_status_allows_legal_transitions(current, action, expected):
    assert next_incident_status(current, action) == expected


@pytest.mark.parametrize(
    "current,action",
    [
        ("ACKNOWLEDGED", "acknowledge"),
        ("INVESTIGATING", "acknowledge"),
        ("INVESTIGATING", "investigate"),
        ("RESOLVED", "acknowledge"),
        ("RESOLVED", "investigate"),
        ("RESOLVED", "resolve"),
        ("UNKNOWN", "resolve"),
        ("DETECTED", "unsupported-action"),
    ],
)
def test_next_incident_status_rejects_illegal_transitions(current, action):
    with pytest.raises(ValueError):
        next_incident_status(current, action)
