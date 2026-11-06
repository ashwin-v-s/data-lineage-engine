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
from backend.app.api.routes.membership import require_role
from backend.app.services.freshness import (
    evaluate_freshness,
    incident_dedupe_key,
    incident_severity_for_state,
    next_incident_status,
)
from backend.app.services.freshness_evidence import last_successful_runtime_activity
from backend.app.services.freshness_scheduler import scheduler_status

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
    COALESCE(i.assigned_user_id, i.owner_user_id)::text AS owner_user_id,
    i.detail                                    AS detail,
    i.resolution_detail                         AS resolution_detail
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
    evaluation_schedule: Literal["manual", "15m", "hourly", "daily"] = "manual"
    paused: bool = False

    @model_validator(mode="after")
    def _require_error_above_warn(self) -> "SlaInput":
        if self.error_after_minutes <= self.warn_after_minutes:
            raise ValueError("error_after_minutes must be greater than warn_after_minutes")
        expected_warn = max(1, int(self.error_after_minutes * 0.8))
        if self.warn_after_minutes != expected_warn:
            raise ValueError("warn_after_minutes must be exactly 80% of the SLA duration (error_after_minutes)")
        return self


class FreshnessConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observed_at: datetime
    note: str = Field(min_length=1, max_length=1000)


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
    """Fail closed until the approved M4 extension is installed."""
    tables = tuple(dict.fromkeys((*tables, "freshness_confirmation")))
    missing: list[str] = []
    for table in tables:
        cur.execute("SELECT to_regclass(%s) AS relation", (f"public.{table}",))
        if cur.fetchone()["relation"] is None:
            missing.append(table)
    if missing:
        raise HTTPException(
            status_code=503,
            detail=(
                "The required governance storage is not installed in this project "
                f"(missing: {', '.join(missing)}). Migration 0011 is proposal-only and requires migration-owner approval."
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
        "evaluation_schedule": row.get("evaluation_schedule", "manual"),
        "scheduler_status": scheduler_status(row.get("evaluation_schedule", "manual")),
        "paused": bool(row.get("paused", False)),
        "created_at": row["created_at"],
    }


@router.post("/slas", dependencies=[Depends(require_role("owner", "admin", "editor"))])
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
                     stale_after_minutes, signal, evaluation_schedule, paused)
                VALUES (%s::uuid, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (workspace_id, dataset_id) DO UPDATE
                    SET warn_after_minutes = EXCLUDED.warn_after_minutes,
                        error_after_minutes = EXCLUDED.error_after_minutes,
                        stale_after_minutes = EXCLUDED.stale_after_minutes,
                        signal = EXCLUDED.signal,
                        evaluation_schedule = EXCLUDED.evaluation_schedule,
                        paused = EXCLUDED.paused
                RETURNING id::text AS id,
                          dataset_id::text AS dataset_id,
                          warn_after_minutes,
                          error_after_minutes,
                          stale_after_minutes,
                          signal, evaluation_schedule, paused,
                          {_TS.format(col='created_at')} AS created_at
                """,
                (
                    dataset["id"],
                    request.warn_after_minutes,
                    request.error_after_minutes,
                    request.stale_after_minutes,
                    request.signal,
                    request.evaluation_schedule,
                    request.paused,
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
                       s.evaluation_schedule               AS evaluation_schedule,
                       s.paused                            AS paused,
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
                       e.evidence_ref                         AS evidence_ref,
                       e.evaluation_mode                      AS evaluation_mode,
                       {_TS.format(col='e.evaluated_at')}     AS evaluated_at
                FROM   freshness_evaluation e
                JOIN   dataset d ON d.id = e.dataset_id
                ORDER  BY e.dataset_id, e.evaluated_at DESC
                """
            )
            rows = cur.fetchall()
    evaluations = [dict(row) for row in rows]
    counts = {state: 0 for state in ("HEALTHY", "AT_RISK", "LATE", "STALE", "UNKNOWN", "PAUSED")}
    for item in evaluations:
        if item["state"] in counts:
            counts[item["state"]] += 1
    return {"evaluations": evaluations, "counts": counts, "total": len(evaluations)}


def _last_source_activity(cur, dataset_id: str, signal: str | None):
    """Return authoritative freshness evidence, or None (UNKNOWN).

    Ingestion time and lineage writes do not prove a successful source run.
    Only a manual confirmation or a positive OpenLineage observation joined
    to a canonical completed run is accepted.
    """
    if signal == "manual":
        cur.execute("SELECT observed_at AS last_activity, NULL::uuid AS evidence_id, jsonb_build_object('kind','MANUAL_CONFIRMATION','confirmation_id',id::text,'confirmed_by',confirmed_by::text,'note',note,'recorded_at',created_at) AS evidence_ref FROM freshness_confirmation WHERE dataset_id=%s::uuid ORDER BY observed_at DESC LIMIT 1", (dataset_id,))
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
    cur.execute("SELECT user_id::text FROM workspace_member WHERE user_id=%s::uuid AND status='active'", (owner,))
    member = cur.fetchone()
    return member["user_id"] if member else None


@router.post("/datasets/{asset_id}/evaluate", dependencies=[Depends(require_role("owner", "admin", "editor"))])
def evaluate_dataset(asset_id: uuid.UUID, user: dict = Depends(require_user)):
    """Run the freshness engine for one dataset and reconcile its incident."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_governance(cur, "freshness_sla", "freshness_evaluation", "incident", "incident_event", "freshness_confirmation")
            dataset = _resolve_dataset(cur, str(asset_id))
            if not dataset:
                raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found.")
            dataset_id = dataset["id"]

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
            evidence_id = str(activity["evidence_id"]) if activity and activity.get("evidence_id") else None
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
                VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s::uuid, %s, 'MANUAL', %s)
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
                    Json(activity.get("evidence_ref") if activity and activity.get("evidence_ref") else ({"kind": "EVIDENCE", "evidence_id": evidence_id} if evidence_id else {"kind": "UNAVAILABLE", "reason": "No supported evidence signal was found."})),
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
                    "evidence_id": evidence_id,
                    "evidence_ref": activity.get("evidence_ref") if activity else None,
                }
            )

            incident_action = "none"
            incident_id: str | None = None

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

            # State snapshots and their source evidence share one transaction.
            # Subscribers must refetch via the authorized API; no sensitive
            # row is broadcast through Realtime.
            if verdict.state in ("LATE", "STALE") and incident_action == "created":
                if owner_user_id:
                    _create_in_app_notification(cur, owner_user_id, "FRESHNESS_BREACH", f"{dataset['name']} is {verdict.state}", {"dataset_id": dataset_id, "incident_id": incident_id, "evaluation_id": evaluation_id}, f"/governance/freshness?asset={dataset_id}")

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


@router.post("/datasets/{asset_id}/confirm-freshness", status_code=201, dependencies=[Depends(require_role("owner", "admin", "editor"))])
def confirm_freshness(asset_id: uuid.UUID, body: FreshnessConfirmation, user: dict = Depends(require_user)):
    """Record a human freshness attestation as MANUAL evidence, never runtime evidence."""
    observed = body.observed_at
    if observed.tzinfo is None:
        raise HTTPException(status_code=422, detail="observed_at must include a timezone")
    if observed > datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="observed_at cannot be in the future")
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_governance(cur, "freshness_confirmation")
            dataset = _resolve_dataset(cur, str(asset_id))
            if not dataset:
                raise HTTPException(status_code=404, detail="Asset not found")
            cur.execute("INSERT INTO freshness_confirmation(dataset_id,observed_at,note,confirmed_by) VALUES (%s::uuid,%s,%s,%s::uuid) RETURNING id::text,observed_at,created_at,confirmed_by::text", (dataset["id"], observed.astimezone(timezone.utc), body.note.strip(), user["id"]))
            row = dict(cur.fetchone())
    return {"ok": True, "evidence_kind": "MANUAL", "runtime_observation": False, "confirmation": row}


def _create_in_app_notification(cur, recipient_id, event_type, title, detail, action_path):
    """Best-effort schema guard; notification storage stays transaction-local."""
    cur.execute("SELECT to_regclass('public.notification') AS relation")
    if cur.fetchone()["relation"] is None:
        return
    cur.execute(
        """INSERT INTO notification (recipient_user_id,event_type,title,detail,action_path)
           VALUES (%s::uuid,%s,%s,%s,%s)""",
        (recipient_id, event_type, title, Json(detail), action_path),
    )


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
    cur.execute(
        """SELECT id::text,title,severity,status,opened_at
           FROM incident WHERE dataset_id=%s::uuid AND id<>%s::uuid
           ORDER BY opened_at DESC LIMIT 5""",
        (incident["dataset_id"], incident_id),
    )
    incident["related_incidents"] = [dict(item) for item in cur.fetchall()]
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


class IncidentResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=2000)
    action_taken: str = Field(min_length=1, max_length=2000)


class IncidentComment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    comment: str = Field(min_length=1, max_length=4000)


class IncidentAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: uuid.UUID


def _apply_transition(incident_id: uuid.UUID, action: str, user: dict, resolution: IncidentResolution | None = None) -> dict:
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
                    "UPDATE incident SET status = %s, resolved_at = now(), resolution_detail = %s WHERE id = %s::uuid",
                    (new_status, Json({"reason": resolution.reason.strip(), "action_taken": resolution.action_taken.strip(), "resolved_by": user["id"]}) if resolution else Json({}), str(incident_id)),
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


@router.post("/incidents/{incident_id}/acknowledge", dependencies=[Depends(require_role("owner", "admin", "editor"))])
def acknowledge_incident(incident_id: uuid.UUID, user: dict = Depends(require_user)):
    """Transition an incident to ACKNOWLEDGED (409 on an illegal transition)."""
    return _apply_transition(incident_id, "acknowledge", user)


@router.post("/incidents/{incident_id}/investigate", dependencies=[Depends(require_role("owner", "admin", "editor"))])
def investigate_incident(incident_id: uuid.UUID, user: dict = Depends(require_user)):
    """Transition an incident to INVESTIGATING (409 on an illegal transition)."""
    return _apply_transition(incident_id, "investigate", user)


@router.post("/incidents/{incident_id}/resolve", dependencies=[Depends(require_role("owner", "admin", "editor"))])
def resolve_incident(incident_id: uuid.UUID, body: IncidentResolution, user: dict = Depends(require_user)):
    """Resolve only with auditable reason and action details."""
    return _apply_transition(incident_id, "resolve", user, body)


@router.post("/incidents/{incident_id}/comments", status_code=201, dependencies=[Depends(require_role("owner", "admin", "editor"))])
def comment_on_incident(incident_id: uuid.UUID, body: IncidentComment, user: dict = Depends(require_user)):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_governance(cur, "incident", "incident_event")
            cur.execute("SELECT id FROM incident WHERE id=%s::uuid AND status <> 'RESOLVED'", (str(incident_id),))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Open incident not found")
            cur.execute("INSERT INTO incident_event(incident_id,event_type,actor_user_id,detail) VALUES (%s::uuid,'COMMENTED',%s::uuid,%s) RETURNING id::text,created_at", (str(incident_id),user["id"],Json({"comment": body.comment.strip()})))
            event = dict(cur.fetchone())
    return {"ok": True, "event": event}


@router.post("/incidents/{incident_id}/assign", dependencies=[Depends(require_role("owner", "admin"))])
def assign_incident(incident_id: uuid.UUID, body: IncidentAssignment, user: dict = Depends(require_user)):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_governance(cur, "incident", "incident_event", "workspace_member")
            cur.execute("SELECT user_id FROM workspace_member WHERE user_id=%s::uuid AND status='active'", (str(body.user_id),))
            if not cur.fetchone():
                raise HTTPException(status_code=422, detail="Assignee must be an active member of this workspace")
            cur.execute("UPDATE incident SET assigned_user_id=%s::uuid WHERE id=%s::uuid RETURNING id::text", (str(body.user_id),str(incident_id)))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Incident not found")
            cur.execute("INSERT INTO incident_event(incident_id,event_type,actor_user_id,detail) VALUES (%s::uuid,'COMMENTED',%s::uuid,%s)", (str(incident_id),user["id"],Json({"assignment": "changed", "assigned_user_id": str(body.user_id)})))
            _create_in_app_notification(cur, str(body.user_id), "INCIDENT_CREATED", "Incident assigned to you", {"incident_id": str(incident_id)}, f"/governance/incidents/{incident_id}")
    return {"ok": True, "assigned_user_id": str(body.user_id)}
