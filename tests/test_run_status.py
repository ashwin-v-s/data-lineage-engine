"""Tests for the run-status presentation mapping.

The database stores pipeline lifecycle values; the Runs view filters on the
UI vocabulary. The mapping must never turn an unknown value into SUCCESS.
"""
from __future__ import annotations

import pytest

from backend.app.services.run_status import ui_run_status


@pytest.mark.parametrize(
    "stored,expected",
    [
        ("completed", "SUCCESS"),
        ("COMPLETED", "SUCCESS"),
        ("success", "SUCCESS"),
        ("succeeded", "SUCCESS"),
        ("failed", "FAILED"),
        ("FAILURE", "FAILED"),
        ("error", "FAILED"),
        ("running", "RUNNING"),
        ("started", "RUNNING"),
        ("aborted", "ABORTED"),
        ("cancelled", "ABORTED"),
        ("canceled", "ABORTED"),
    ],
)
def test_known_statuses_map_to_the_ui_vocabulary(stored, expected):
    assert ui_run_status(stored) == expected


def test_unknown_and_missing_statuses_never_become_success():
    assert ui_run_status("queued") == "QUEUED"
    assert ui_run_status("weird_state") == "WEIRD_STATE"
    assert ui_run_status(None) == "UNKNOWN"
    assert ui_run_status("") == "UNKNOWN"
    assert ui_run_status("   ") == "UNKNOWN"


def test_mapping_covers_the_statuses_the_runs_view_filters_on():
    filters = {"SUCCESS", "RUNNING", "WARNING", "FAILED", "ABORTED"}
    produced = {ui_run_status(value) for value in ("completed", "running", "failed", "aborted")}
    assert produced <= filters
