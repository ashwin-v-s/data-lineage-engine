"""Presentation mapping for stored execution-run statuses.

The database stores run lifecycle values (``running``/``completed``/``failed``)
because that is what a pipeline reports. The catalog read model exposes the
vocabulary the Runs view filters on (``SUCCESS``/``FAILED``/``RUNNING``/…).
Keeping the mapping here means the API cannot drift from the UI's filter list,
and an unrecognised stored value is surfaced upper-cased rather than silently
dropped.
"""
from __future__ import annotations

from typing import Any

_RUN_STATUS = {
    "completed": "SUCCESS",
    "complete": "SUCCESS",
    "success": "SUCCESS",
    "succeeded": "SUCCESS",
    "failed": "FAILED",
    "failure": "FAILED",
    "error": "FAILED",
    "running": "RUNNING",
    "started": "RUNNING",
    "aborted": "ABORTED",
    "cancelled": "ABORTED",
    "canceled": "ABORTED",
}


def ui_run_status(status: Any) -> str:
    """Map a stored run status to the UI vocabulary without inventing success."""
    text = str(status or "").strip()
    if not text:
        return "UNKNOWN"
    return _RUN_STATUS.get(text.lower(), text.upper())
