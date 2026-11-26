"""Shared freshness evaluation runner for manual and scheduled triggers.

The route and the scheduler use this module so both paths persist the same
evidence, reconcile incidents the same way, and create the same notification.
Scheduled evaluation has no human actor, so incident events record no actor.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from psycopg2.extras import Json, RealDictCursor

from backend.app.db import (
    get_conn,
    list_freshness_targets,
    reset_workspace_id,
    set_workspace_id,
)
from backend.app.services.freshness import (
    FreshnessVerdict,
    evaluate_freshness,
    incident_dedupe_key,
    incident_severity_for_state,
)
from backend.app.services.freshness_evidence import last_successful_runtime_activity
from backend.app.services.notification_delivery import (
    NotificationMessage,
    create_in_app_notification,
    dispatch_notification_emails,
)

logger = logging.getLogger(__name__)

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FreshnessRun:
    verdict: FreshnessVerdict
    evaluation_id: str
    incident_action: str
    incident_id: str | None
    notification: NotificationMessage | None


def _last_source_activity(cur, dataset_id: str, signal: str | None):
    """Return authoritative freshness evidence, or None (UNKNOWN).

    Ingestion time and lineage writes do not prove a successful source run.
    Only a manual confirmation or a positive OpenLineage observation joined
    to a canonical completed run is accepted.
    """
    if signal == "manual":
        cur.execute(
            "SELECT observed_at AS last_activity, NULL::uuid AS evidence_id, "
            "jsonb_build_object('kind','MANUAL_CONFIRMATION','confirmation_id',id::text,"
            "'confirmed_by',confirmed_by::text,'note',note,'recorded_at',created_at) AS evidence_ref "
            "FROM freshness_confirmation WHERE dataset_id=%s::uuid "
            "ORDER BY observed_at DESC LIMIT 1",
            (dataset_id,),
        )
        return cur.fetchone()
    if signal != "openlineage_run":
        # dbt run_results and source updated_at are not yet persisted by the
        # M2/M3 contract in a source-verifiable form, so neither may imply stale.
        return None
    return last_successful_runtime_activity(cur, dataset_id)


def _open_incident_id(cur, dedupe_key: str) -> str | None:
    cur.execute(
        """
        SELECT id::text AS id FROM incident
        WHERE dedupe_key = %s AND status <> 'RESOLVED'
        ORDER BY opened_at DESC
        LIMIT 1
        """,
        (dedupe_key,),
    )
    row = cur.fetchone()
    return row["id"] if row else None


def _workspace_owner_id(cur, dataset_id: str) -> str | None:
    """Resolve a dataset owner only when its stored identifier is a workspace user UUID."""
    cur.execute("SELECT owner_id FROM dataset WHERE id=%s::uuid", (dataset_id,))
    row = cur.fetchone()
    owner = str(row["owner_id"] or "") if row else ""
    if not _UUID_RE.fullmatch(owner):
        return None
    cur.execute("SELECT to_regclass('public.workspace_member') AS relation")
    if cur.fetchone()["relation"] is None:
        return None
    cur.execute(
        "SELECT user_id::text FROM workspace_member WHERE user_id=%s::uuid AND status='active'",
        (owner,),
    )
    member = cur.fetchone()
    return member["user_id"] if member else None


def evaluate_dataset_freshness(
    cur,
    dataset_id: str,
    *,
    actor_user_id: str | None,
    mode: str = "MANUAL",
) -> FreshnessRun:
    """Evaluate one dataset, reconcile its incident, and stage its notification.

    The caller owns the transaction. Notification email is dispatched by the
    caller only after that transaction commits.
    """
    if mode not in {"MANUAL", "SCHEDULED"}:
        raise ValueError("Freshness evaluation mode must be MANUAL or SCHEDULED")

    cur.execute(
        "SELECT id::text AS id, name FROM dataset WHERE id = %s::uuid LIMIT 1",
        (dataset_id,),
    )
    dataset = cur.fetchone()
    if not dataset:
        raise LookupError(f"Dataset '{dataset_id}' not found")

    cur.execute(
        """
        SELECT id::text AS id, warn_after_minutes, error_after_minutes,
               stale_after_minutes, signal, paused
        FROM   freshness_sla
        WHERE  dataset_id = %s::uuid
        LIMIT  1
        """,
        (dataset_id,),
    )
    sla = cur.fetchone()

    signal = sla["signal"] if sla else None
    activity = _last_source_activity(cur, dataset_id, signal)
    last_activity = activity["last_activity"] if activity else None
    evidence_id = (
        str(activity["evidence_id"])
        if activity and activity.get("evidence_id")
        else None
    )
    now = datetime.now(timezone.utc)
    verdict = evaluate_freshness(
        last_source_activity_at=last_activity,
        now=now,
        warn_after_minutes=sla["warn_after_minutes"] if sla else None,
        error_after_minutes=sla["error_after_minutes"] if sla else None,
        stale_after_minutes=sla["stale_after_minutes"] if sla else None,
        paused=bool(sla and sla["paused"]),
    )

    cur.execute(
        """
        INSERT INTO freshness_evaluation
            (dataset_id, sla_id, state, age_minutes, threshold_minutes, reason,
             last_source_activity_at, evidence_id, evidence_ref, evaluation_mode, evaluated_at)
        VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s::uuid, %s, %s, %s)
        RETURNING id::text AS id
        """,
        (
            dataset_id,
            sla["id"] if sla else None,
            verdict.state,
            verdict.age_minutes,
            verdict.threshold_minutes,
            verdict.reason,
            last_activity,
            evidence_id,
            Json(
                activity.get("evidence_ref")
                if activity and activity.get("evidence_ref")
                else (
                    {"kind": "EVIDENCE", "evidence_id": evidence_id}
                    if evidence_id
                    else {
                        "kind": "UNAVAILABLE",
                        "reason": "No supported evidence signal was found.",
                    }
                )
            ),
            mode,
            now,
        ),
    )
    evaluation_id = cur.fetchone()["id"]

    detail = Json(
        {
            "state": verdict.state,
            "reason": verdict.reason,
            "age_minutes": verdict.age_minutes,
            "threshold_minutes": verdict.threshold_minutes,
            "evaluation_id": evaluation_id,
            "evaluation_mode": mode,
            "evidence_id": evidence_id,
            "evidence_ref": activity.get("evidence_ref") if activity else None,
        }
    )

    incident_action = "none"
    incident_id: str | None = None
    owner_user_id: str | None = None

    if verdict.state in ("LATE", "STALE"):
        dedupe_key = incident_dedupe_key(dataset_id)
        owner_user_id = _workspace_owner_id(cur, dataset_id)
        cur.execute(
            """
            INSERT INTO incident
                (dataset_id, title, severity, status, dedupe_key, detail, assigned_user_id)
            VALUES (%s::uuid, %s, %s, 'DETECTED', %s, %s, %s::uuid)
            ON CONFLICT (workspace_id, dedupe_key)
                WHERE status <> 'RESOLVED' DO NOTHING
            RETURNING id::text AS id
            """,
            (
                dataset_id,
                f"{dataset['name']} is {verdict.state}",
                incident_severity_for_state(verdict.state),
                dedupe_key,
                detail,
                owner_user_id,
            ),
        )
        opened = cur.fetchone()
        if opened:
            incident_id = opened["id"]
            incident_action = "created"
            cur.execute(
                """
                INSERT INTO incident_event
                    (incident_id, event_type, actor_user_id, detail)
                VALUES (%s::uuid, 'DETECTED', %s::uuid, %s)
                """,
                (incident_id, actor_user_id, detail),
            )
        else:
            incident_action = "existing"
            incident_id = _open_incident_id(cur, dedupe_key)
    elif verdict.state in ("HEALTHY", "AT_RISK"):
        dedupe_key = incident_dedupe_key(dataset_id)
        open_id = _open_incident_id(cur, dedupe_key)
        if open_id:
            incident_id = open_id
            incident_action = "resolved"
            cur.execute(
                """
                UPDATE incident
                SET    status = 'RESOLVED', resolved_at = now()
                WHERE  id = %s::uuid
                """,
                (incident_id,),
            )
            cur.execute(
                """
                INSERT INTO incident_event
                    (incident_id, event_type, actor_user_id, detail)
                VALUES (%s::uuid, 'RESOLVED', %s::uuid, %s)
                """,
                (incident_id, actor_user_id, detail),
            )

    notification = None
    if verdict.state in ("LATE", "STALE") and incident_action == "created":
        if owner_user_id:
            notification = create_in_app_notification(
                cur,
                owner_user_id,
                "FRESHNESS_BREACH",
                f"{dataset['name']} is {verdict.state}",
                {
                    "dataset_id": dataset_id,
                    "incident_id": incident_id,
                    "evaluation_id": evaluation_id,
                },
                f"/?view=freshness&asset={dataset_id}",
            )

    return FreshnessRun(
        verdict=verdict,
        evaluation_id=evaluation_id,
        incident_action=incident_action,
        incident_id=incident_id,
        notification=notification,
    )


def run_scheduled_freshness() -> dict:
    """Evaluate every due, non-manual SLA under its own workspace RLS scope."""
    targets = list_freshness_targets()
    evaluated = 0
    failed = 0

    for target in targets:
        workspace_id = target["workspace_id"]
        dataset_id = target["dataset_id"]
        token = set_workspace_id(workspace_id)
        try:
            with get_conn() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    run = evaluate_dataset_freshness(
                        cur,
                        dataset_id,
                        actor_user_id=None,
                        mode="SCHEDULED",
                    )
            if run.notification is not None:
                dispatch_notification_emails([run.notification])
            evaluated += 1
        except Exception:
            failed += 1
            logger.exception(
                "Scheduled freshness evaluation failed workspace_id=%s dataset_id=%s",
                workspace_id,
                dataset_id,
            )
        finally:
            reset_workspace_id(token)

    return {"evaluated": evaluated, "failed": failed}
