"""Workspace quality scorecard shared by /quality and /trust.

The scorecard reports only persisted evaluation results. It never estimates a
score for an assertion that has not run, and a pass rate is ``None`` — not 0 —
when no assertion has produced a PASS or FAIL result. SKIPPED and ERROR results
are counted separately because neither is evidence of good or bad data.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

_SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW")


def _value(row: Any, key: str, index: int) -> Any:
    """Read a column from a dict-like or tuple row."""
    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        try:
            return row[index]
        except (KeyError, TypeError, IndexError):
            return None


def _rate(passed: int, failed: int) -> float | None:
    total = passed + failed
    if total <= 0:
        return None
    return round(passed / total, 4)


def build_scorecard(cur, days: int = 30) -> dict:
    """Build a scorecard from the latest result per enabled assertion.

    ``days`` bounds only the trend series; the snapshot always uses the newest
    stored result per assertion.
    """
    cur.execute(
        """
        SELECT a.severity, latest.status
        FROM   quality_assertion a
        LEFT JOIN LATERAL (
            SELECT status FROM quality_result r
            WHERE  r.assertion_id = a.id
            ORDER  BY r.evaluated_at DESC
            LIMIT  1
        ) latest ON TRUE
        WHERE  a.enabled
        """
    )
    rows = cur.fetchall()

    totals = {"assertions": 0, "evaluated": 0, "passing": 0, "failing": 0, "skipped": 0, "errored": 0}
    by_severity = {severity: {"severity": severity, "assertions": 0, "passing": 0, "failing": 0} for severity in _SEVERITIES}
    for row in rows:
        status = _value(row, "status", 1)
        severity = _value(row, "severity", 0)
        totals["assertions"] += 1
        bucket = by_severity.setdefault(
            severity or "UNSPECIFIED",
            {"severity": severity or "UNSPECIFIED", "assertions": 0, "passing": 0, "failing": 0},
        )
        bucket["assertions"] += 1
        if status is None:
            continue
        totals["evaluated"] += 1
        if status == "PASS":
            totals["passing"] += 1
            bucket["passing"] += 1
        elif status == "FAIL":
            totals["failing"] += 1
            bucket["failing"] += 1
        elif status == "SKIPPED":
            totals["skipped"] += 1
        else:
            totals["errored"] += 1

    for bucket in by_severity.values():
        bucket["pass_rate"] = _rate(bucket["passing"], bucket["failing"])
    totals["pass_rate"] = _rate(totals["passing"], totals["failing"])
    totals["unevaluated"] = totals["assertions"] - totals["evaluated"]

    cur.execute(
        """
        SELECT to_char(date_trunc('day', evaluated_at), 'YYYY-MM-DD') AS day,
               count(*)::int AS evaluated,
               count(*) FILTER (WHERE status = 'PASS')::int AS passed,
               count(*) FILTER (WHERE status = 'FAIL')::int AS failed,
               count(*) FILTER (WHERE status = 'SKIPPED')::int AS skipped,
               count(*) FILTER (WHERE status IN ('ERROR'))::int AS errored
        FROM   quality_result
        WHERE  evaluated_at >= now() - make_interval(days => %s)
        GROUP  BY 1
        ORDER  BY 1
        """,
        (days,),
    )
    trend = []
    for row in cur.fetchall():
        passed = int(_value(row, "passed", 2) or 0)
        failed = int(_value(row, "failed", 3) or 0)
        trend.append(
            {
                "day": _value(row, "day", 0),
                "evaluated": int(_value(row, "evaluated", 1) or 0),
                "passed": passed,
                "failed": failed,
                "skipped": int(_value(row, "skipped", 4) or 0),
                "errored": int(_value(row, "errored", 5) or 0),
                "pass_rate": _rate(passed, failed),
            }
        )

    cur.execute(
        """
        SELECT count(*)::int AS count
        FROM   dataset d
        WHERE  NOT EXISTS (
            SELECT 1 FROM quality_assertion a
            WHERE  a.dataset_id = d.id AND a.enabled
        )
        """
    )
    uncovered = cur.fetchone()
    uncovered_assets = int(_value(uncovered, "count", 0) or 0)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": days,
        "summary": totals,
        "by_severity": [by_severity[severity] for severity in _SEVERITIES if severity in by_severity]
        + [bucket for severity, bucket in by_severity.items() if severity not in _SEVERITIES],
        "trend": trend,
        "uncovered_assets": uncovered_assets,
        "semantics": (
            "Pass rate counts PASS and FAIL results only. SKIPPED and ERROR are reported separately, "
            "and an unevaluated assertion is never scored."
        ),
    }
