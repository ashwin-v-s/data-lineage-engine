"""
backend/app/api/routes/governance.py
────────────────────────────────────
Governance: freshness SLAs, the freshness engine, and incidents.

Endpoints
─────────
  POST   /api/v1/governance/slas                                  create/update an SLA
  GET    /api/v1/governance/slas                                  list SLAs
  GET    /api/v1/governance/freshness                             latest verdict per dataset
  POST   /api/v1/governance/datasets/{asset_id}/evaluate          run the freshness engine
  GET    /api/v1/governance/incidents                             list incidents
  GET    /api/v1/governance/incidents/{incident_id}               one incident + its events
  POST   /api/v1/governance/incidents/{incident_id}/acknowledge   acknowledge
  POST   /api/v1/governance/incidents/{incident_id}/investigate   investigate
  POST   /api/v1/governance/incidents/{incident_id}/resolve        resolve

Every evaluation is driven by **stored evidence** only.  The engine never
substitutes the current time for missing source activity: an unobserved dataset
is reported ``UNKNOWN``, never ``LATE``.  Exactly one incident is opened per
active breach, deduplicated on ``(workspace_id, dedupe_key)``; a return to
``HEALTHY``/``AT_RISK`` resolves the open incident.

The workspace comes from ``get_conn()`` (server-side), never from the client,
and every route requires a verified user.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg2.extras import Json, RealDictCursor
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.auth import require_user
from backend.app.db import get_conn
from backend.app.services.freshness import (
    evaluate_freshness,
    incident_dedupe_key,
    incident_severity_for_state,
    next_incident_status,
)

router = APIRouter(prefix="/governance", tags=["governance"], dependencies=[Depends(require_user)])

_UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE,
)

_TS = "to_char({col} AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\"')"

_INCIDENT_COLUMNS = f"""
    i.id::text                                  AS id,
    i.dataset_id::text                          AS dataset_id,
    d.name                                      AS dataset_name,
    i.title                                     AS title,
    i.severity                                  AS severity,
    i.status                                    AS status,
    i.dedupe_key                                AS dedupe_key,
    {_TS.format(col='i.opened_at')}             AS opened_at,
    {_TS.format(col='i.acknowledged_at')}       AS acknowledged_at,
    {_TS.format(col='i.resolved_at')}           AS resolved_at,
    i.owner_user_id::text                       AS owner_user_id,
    i.detail                                    AS detail
"""

_EVENT_COLUMNS = f"""
    ev.id::text                                 AS id,
    ev.event_type                               AS event_type,
    ev.actor_user_id::text                      AS actor_user_id,
    ev.detail                                   AS detail,
    {_TS.format(col='ev.created_at')}           AS created_at
"""


class SlaInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1, max_length=512)
    warn_after_minutes: int = Field(ge=1)
    error_after_minutes: int = Field(ge=1)
    stale_after_minutes: int | None = Field(default=None, ge=1)
    signal: Literal["openlineage_run", "dbt_run_results", "updated_at", "manual"]

    @model_validator(mode="after")
    def _require_error_above_warn(self) -> "SlaInput":
        if self.error_after_minutes <= self.warn_after_minutes:
            raise ValueError("error_after_minutes must be greater than warn_after_minutes")
        return self


def _resolve_dataset(cur, asset_id: str) -> dict | None:
    """Resolve an asset UUID or dataset name to a workspace dataset row."""
    if _UUID_RE.match(asset_id):
        cur.execute(
            "SELECT id::text AS id, name FROM dataset WHERE id = %s::uuid LIMIT 1",
            (asset_id,),
        )
        row = cur.fetchone()
        if row:
            return row
    cur.execute(
        """
        SELECT id::text AS id, name FROM dataset
        WHERE lower(name) = lower(%s)
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (asset_id,),
    )
    return cur.fetchone()


def _require_governance(cur, *tables: str) -> None:
    """Fail honestly with HTTP 503 until the governance migration is applied."""
    missing: list[str] = []
    for table in tables:
        cur.execute("SELECT to_regclass(%s) AS relation", (f"public.{table}",))
        if cur.fetchone()["relation"] is None:
            missing.append(table)
    if missing:
        raise HTTPException(
            status_code=503,
            detail=(
                "The governance migration is not installed in this Supabase project "
                f"(missing: {', '.join(missing)}). Apply migration 0009_governance.sql first."
            ),
        )


def _serialize_sla(row) -> dict:
    return {
        "id": row["id"],
        "dataset_id": row["dataset_id"],
        "dataset_name": row.get("dataset_name"),
        "warn_after_minutes": row["warn_after_minutes"],
        "error_after_minutes": row["error_after_minutes"],
        "stale_after_minutes": row["stale_after_minutes"],
        "signal": row["signal"],
        "created_at": row["created_at"],
    }


@router.post("/slas")
def upsert_sla(request: SlaInput, user: dict = Depends(require_user)):
    """Create or replace the freshness SLA for one dataset."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_governance(cur, "freshness_sla")
            dataset = _resolve_dataset(cur, request.asset_id)
            if not dataset:
                raise HTTPException(status_code=404, detail=f"Asset '{request.asset_id}' not found.")
            cur.execute(
                f"""
                INSERT INTO freshness_sla
                    (dataset_id, warn_after_minutes, error_after_minutes,
                     stale_after_minutes, signal)
                VALUES (%s::uuid, %s, %s, %s, %s)
                ON CONFLICT (workspace_id, dataset_id) DO UPDATE
                    SET warn_after_minutes = EXCLUDED.warn_after_minutes,
                        error_after_minutes = EXCLUDED.error_after_minutes,
                        stale_after_minutes = EXCLUDED.stale_after_minutes,
                        signal = EXCLUDED.signal
                RETURNING id::text AS id,
                          dataset_id::text AS dataset_id,
                          warn_after_minutes,
                          error_after_minutes,
                          stale_after_minutes,
                          signal,
                          {_TS.format(col='created_at')} AS created_at
                """,
                (
                    dataset["id"],
                    request.warn_after_minutes,
                    request.error_after_minutes,
                    request.stale_after_minutes,
                    request.signal,
                ),
            )
            saved = dict(cur.fetchone())
            saved["dataset_name"] = dataset["name"]
    return _serialize_sla(saved)


@router.get("/slas")
def list_slas(user: dict = Depends(require_user)):
    """List the workspace's freshness SLAs with a human-readable dataset name."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_governance(cur, "freshness_sla")
            cur.execute(
                f"""
                SELECT s.id::text                          AS id,
                       s.dataset_id::text                  AS dataset_id,
                       d.name                              AS dataset_name,
                       s.warn_after_minutes                AS warn_after_minutes,
                       s.error_after_minutes               AS error_after_minutes,
                       s.stale_after_minutes               AS stale_after_minutes,
                       s.signal                            AS signal,
                       {_TS.format(col='s.created_at')}    AS created_at
                FROM   freshness_sla s
                JOIN   dataset d ON d.id = s.dataset_id
                ORDER  BY s.created_at DESC
                """
            )
            rows = cur.fetchall()
    slas = [_serialize_sla(row) for row in rows]
    return {"slas": slas, "count": len(slas)}


@router.get("/freshness")
def list_freshness(user: dict = Depends(require_user)):
    """Return the latest freshness verdict per dataset plus counts by state."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_governance(cur, "freshness_evaluation")
            cur.execute(
                f"""
                SELECT DISTINCT ON (e.dataset_id)
                       e.id::text                             AS id,
                       e.dataset_id::text                     AS dataset_id,
                       d.name                                 AS dataset_name,
                       e.state                                AS state,
                       e.age_minutes                          AS age_minutes,
                       e.threshold_minutes                    AS threshold_minutes,
                       e.reason                               AS reason,
                       {_TS.format(col='e.last_source_activity_at')} AS last_source_activity_at,
                       e.evidence_id::text                    AS evidence_id,
                       {_TS.format(col='e.evaluated_at')}     AS evaluated_at
                FROM   freshness_evaluation e
                JOIN   dataset d ON d.id = e.dataset_id
                ORDER  BY e.dataset_id, e.evaluated_at DESC
                """
            )
            rows = cur.fetchall()
    evaluations = [dict(row) for row in rows]
    counts = {state: 0 for state in ("HEALTHY", "AT_RISK", "LATE", "STALE", "UNKNOWN")}
    for item in evaluations:
        if item["state"] in counts:
            counts[item["state"]] += 1
    return {"evaluations": evaluations, "counts": counts, "total": len(evaluations)}


def _last_source_activity(cur, dataset_id: str):
    """Return the newest stored evidence timestamp for a dataset, or None.

    Only stored evidence counts: (a) the dataset's own ``evidence`` rows and
    their source ``raw_event``, and (b) the ``edge_temporal_version`` rows of
    any lineage edge touching the dataset.  ``None`` means "no observed source
    activity" — the engine must never substitute the current time.
    """
    cur.execute(
        """
        SELECT max(activity.ts) AS last_activity
        FROM (
            SELECT e.ingestion_time AS ts
            FROM   evidence e
            WHERE  e.source_dataset_id = %(dataset)s::uuid
               OR  e.target_dataset_id = %(dataset)s::uuid
            UNION ALL
            SELECT re.ingestion_time AS ts
            FROM   evidence e
            JOIN   raw_event re ON re.event_id = e.raw_event_id
            WHERE  e.source_dataset_id = %(dataset)s::uuid
               OR  e.target_dataset_id = %(dataset)s::uuid
            UNION ALL
            SELECT etv.transaction_from AS ts
            FROM   edge_temporal_version etv
            JOIN   lineage_edge le ON le.id = etv.edge_id
            WHERE  le.source_id = %(dataset)s::uuid
               OR  le.target_id = %(dataset)s::uuid
        ) activity
        """,
        {"dataset": dataset_id},
    )
    row = cur.fetchone()
    return row["last_activity"] if row else None


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


@router.post("/datasets/{asset_id}/evaluate")
def evaluate_dataset(asset_id: uuid.UUID, user: dict = Depends(require_user)):
    """Run the freshness engine for one dataset and reconcile its incident."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_governance(cur, "freshness_sla", "freshness_evaluation", "incident", "incident_event")
            dataset = _resolve_dataset(cur, str(asset_id))
            if not dataset:
                raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found.")
            dataset_id = dataset["id"]

            cur.execute(
                """
                SELECT id::text AS id, warn_after_minutes, error_after_minutes,
                       stale_after_minutes, signal
                FROM   freshness_sla
                WHERE  dataset_id = %s::uuid
                LIMIT  1
                """,
                (dataset_id,),
            )
            sla = cur.fetchone()

            last_activity = _last_source_activity(cur, dataset_id)
            now = datetime.now(timezone.utc)
            verdict = evaluate_freshness(
                last_source_activity_at=last_activity,
                now=now,
                warn_after_minutes=sla["warn_after_minutes"] if sla else None,
                error_after_minutes=sla["error_after_minutes"] if sla else None,
                stale_after_minutes=sla["stale_after_minutes"] if sla else None,
            )

            cur.execute(
                """
                INSERT INTO freshness_evaluation
                    (dataset_id, sla_id, state, age_minutes, threshold_minutes, reason,
                     last_source_activity_at, evaluated_at)
                VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s)
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
                }
            )

            incident_action = "none"
            incident_id: str | None = None

            if verdict.state in ("LATE", "STALE"):
                dedupe_key = incident_dedupe_key(dataset_id)
                cur.execute(
                    """
                    INSERT INTO incident
                        (dataset_id, title, severity, status, dedupe_key, detail)
                    VALUES (%s::uuid, %s, %s, 'DETECTED', %s, %s)
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
                        (incident_id, user["id"], detail),
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
                        (incident_id, user["id"], detail),
                    )

    return {
        "verdict": {
            "state": verdict.state,
            "age_minutes": verdict.age_minutes,
            "threshold_minutes": verdict.threshold_minutes,
            "reason": verdict.reason,
        },
        "incident_action": incident_action,
        "incident_id": incident_id,
    }


@router.get("/incidents")
def list_incidents(
    status: str | None = Query(default=None),
    user: dict = Depends(require_user),
):
    """List the workspace's incidents, newest first, optionally filtered by status."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_governance(cur, "incident")
            params: list[Any] = []
            where = ""
            if status is not None:
                where = "WHERE i.status = %s"
                params.append(status)
            cur.execute(
                f"""
                SELECT {_INCIDENT_COLUMNS}
                FROM   incident i
                JOIN   dataset d ON d.id = i.dataset_id
                {where}
                ORDER  BY i.opened_at DESC
                """,
                params,
            )
            rows = cur.fetchall()
    incidents = [dict(row) for row in rows]
    return {"incidents": incidents, "count": len(incidents)}


def _incident_detail(cur, incident_id: str) -> dict | None:
    cur.execute(
        f"""
        SELECT {_INCIDENT_COLUMNS}
        FROM   incident i
        JOIN   dataset d ON d.id = i.dataset_id
        WHERE  i.id = %s::uuid
        LIMIT  1
        """,
        (incident_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    incident = dict(row)
    cur.execute(
        f"""
        SELECT {_EVENT_COLUMNS}
        FROM   incident_event ev
        WHERE  ev.incident_id = %s::uuid
        ORDER  BY ev.created_at ASC
        """,
        (incident_id,),
    )
    incident["events"] = [dict(event) for event in cur.fetchall()]
    return incident


@router.get("/incidents/{incident_id}")
def get_incident(incident_id: uuid.UUID, user: dict = Depends(require_user)):
    """Return one incident plus its event timeline, or 404."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_governance(cur, "incident")
            incident = _incident_detail(cur, str(incident_id))
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")
    return incident


def _apply_transition(incident_id: uuid.UUID, action: str, user: dict) -> dict:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_governance(cur, "incident", "incident_event")
            cur.execute(
                "SELECT id::text AS id, status FROM incident WHERE id = %s::uuid FOR UPDATE",
                (str(incident_id),),
            )
            row = cur.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")
            try:
                new_status = next_incident_status(row["status"], action)
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc

            if action == "acknowledge":
                cur.execute(
                    "UPDATE incident SET status = %s, acknowledged_at = now() WHERE id = %s::uuid",
                    (new_status, str(incident_id)),
                )
            elif action == "resolve":
                cur.execute(
                    "UPDATE incident SET status = %s, resolved_at = now() WHERE id = %s::uuid",
                    (new_status, str(incident_id)),
                )
            else:
                cur.execute(
                    "UPDATE incident SET status = %s WHERE id = %s::uuid",
                    (new_status, str(incident_id)),
                )
            cur.execute(
                """
                INSERT INTO incident_event (incident_id, event_type, actor_user_id, detail)
                VALUES (%s::uuid, %s, %s::uuid, %s)
                """,
                (str(incident_id), new_status, user["id"], Json({"action": action})),
            )
            incident = _incident_detail(cur, str(incident_id))
    return incident


@router.post("/incidents/{incident_id}/acknowledge")
def acknowledge_incident(incident_id: uuid.UUID, user: dict = Depends(require_user)):
    """Transition an incident to ACKNOWLEDGED (409 on an illegal transition)."""
    return _apply_transition(incident_id, "acknowledge", user)


@router.post("/incidents/{incident_id}/investigate")
def investigate_incident(incident_id: uuid.UUID, user: dict = Depends(require_user)):
    """Transition an incident to INVESTIGATING (409 on an illegal transition)."""
    return _apply_transition(incident_id, "investigate", user)


@router.post("/incidents/{incident_id}/resolve")
def resolve_incident(incident_id: uuid.UUID, user: dict = Depends(require_user)):
    """Transition an incident to RESOLVED (409 on an illegal transition)."""
    return _apply_transition(incident_id, "resolve", user)
