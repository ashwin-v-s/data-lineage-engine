"""Workspace-scoped governance assertions over Kairos metadata evidence.

This API deliberately evaluates imported metadata only. It never queries a
source database or returns source row values. Assertions about source data are
reported unavailable until M2/M1 provide the authorized, read-only connector
execution contract.
"""
from __future__ import annotations

import uuid
import re
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg2.extras import Json, RealDictCursor
from pydantic import BaseModel, ConfigDict, Field

from backend.app.auth import require_user
from backend.app.db import get_conn
from backend.app.api.routes.membership import require_role
from backend.app.services.freshness_evidence import last_successful_runtime_activity

router = APIRouter(prefix="/quality", tags=["quality"], dependencies=[Depends(require_user)])


class AssertionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: uuid.UUID
    name: str = Field(min_length=1, max_length=160)
    assertion_type: Literal["freshness", "completeness", "uniqueness", "validity", "schema", "custom_sql"]
    definition: dict[str, Any] = Field(default_factory=dict)
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "MEDIUM"
    schedule: Literal["manual", "15m", "hourly", "daily", "on_import"] = "manual"


def _require_tables(cur, *tables: str) -> None:
    missing = []
    for table in tables:
        cur.execute("SELECT to_regclass(%s) AS relation", (f"public.{table}",))
        if cur.fetchone()["relation"] is None:
            missing.append(table)
    if missing:
        raise HTTPException(status_code=503, detail="M4 quality storage is not installed; apply migration 0011_m4_governance.sql after owner review.")


def _result_for_assertion(cur, assertion: dict) -> dict:
    """Evaluate bounded metadata-only assertions; never access source values."""
    dataset_id = assertion["dataset_id"]
    kind = assertion["assertion_type"]
    definition = assertion["definition"] or {}
    checked = failed = 0
    evidence: dict[str, Any] = {"scope": "kairos_metadata", "assertion_type": kind}
    status = "PASS"

    if kind in {"completeness", "schema"}:
        cur.execute("SELECT name, source_system, schema_name FROM dataset WHERE id = %s::uuid", (dataset_id,))
        dataset = cur.fetchone()
        if dataset is None:
            raise HTTPException(status_code=404, detail="Asset not found")
        if kind == "completeness":
            required = definition.get("required_fields", ["name", "source_system", "schema_name"])
            if not isinstance(required, list) or not set(required) <= {"name", "source_system", "schema_name"}:
                raise HTTPException(status_code=422, detail="Completeness required_fields may only reference supported catalog metadata fields.")
            missing = [key for key in required if not str(dataset.get(key) or "").strip()]
            checked, failed = len(required), len(missing)
            evidence["missing_metadata_fields"] = missing
        else:
            expected = definition.get("expected_columns", [])
            if not isinstance(expected, list) or any(not isinstance(v, str) or len(v) > 128 for v in expected):
                raise HTTPException(status_code=422, detail="expected_columns must be a list of names up to 128 characters.")
            cur.execute("SELECT column_name FROM column_record WHERE dataset_id = %s::uuid", (dataset_id,))
            actual = {row["column_name"] for row in cur.fetchall()}
            missing = sorted(set(expected) - actual)
            checked, failed = max(len(expected), 1), len(missing)
            evidence.update({"expected_column_count": len(expected), "observed_column_count": len(actual), "missing_columns": missing})
    elif kind == "uniqueness":
        # Dataset identity is protected by the canonical unique constraint;
        # verify only the metadata identity tuple, never source row keys.
        cur.execute("""SELECT count(*)::int AS n FROM dataset d WHERE d.id = %s::uuid
                       AND EXISTS (SELECT 1 FROM dataset other WHERE other.id <> d.id
                         AND (other.source_system, other.namespace, other.database_name, other.schema_name, other.name, other.asset_type)
                           = (d.source_system, d.namespace, d.database_name, d.schema_name, d.name, d.asset_type))""", (dataset_id,))
        failed = int(cur.fetchone()["n"])
        checked = 1
        evidence["scope"] = "canonical_asset_identity"
    elif kind == "validity":
        expected_type = definition.get("expected_data_type")
        column_name = definition.get("column_name")
        if not isinstance(column_name, str) or not 1 <= len(column_name) <= 128:
            raise HTTPException(status_code=422, detail="Validity checks require a column_name from imported schema metadata.")
        cur.execute("SELECT data_type FROM column_record WHERE dataset_id = %s::uuid AND column_name = %s", (dataset_id, column_name))
        column = cur.fetchone()
        checked = 1
        failed = int(column is None or (expected_type is not None and column["data_type"] != expected_type))
        evidence["column"] = column_name
        evidence["schema_metadata_present"] = column is not None
    elif kind == "freshness":
        row = last_successful_runtime_activity(cur, dataset_id)
        last_activity = row["last_activity"] if row else None
        threshold = definition.get("max_age_minutes")
        if not isinstance(threshold, int) or isinstance(threshold, bool) or not 1 <= threshold <= 525600:
            raise HTTPException(status_code=422, detail="Freshness assertions require max_age_minutes between 1 and 525600.")
        checked = 1
        if last_activity is None:
            status = "SKIPPED"
            evidence.update({"state": "UNKNOWN", "reason": "No stored source activity evidence exists."})
        else:
            from datetime import datetime, timezone
            age = max(0, int((datetime.now(timezone.utc) - last_activity).total_seconds() // 60))
            failed = int(age > threshold)
            evidence.update({"last_source_activity_at": last_activity.isoformat(), "age_minutes": age, "threshold_minutes": threshold, "evidence_id": str(row["evidence_id"]), "run_id": row["run_id"], "evidence_ref": row["evidence_ref"]})
    else:
        status = "SKIPPED"
        evidence.update({"supported": False, "reason": "Custom SQL is not executed: this deployment has no reviewed data:preview grant or isolated source-query runner."})

    if status != "SKIPPED":
        status = "FAIL" if failed else "PASS"
    return {"status": status, "checked_count": checked, "failed_count": failed, "evidence": evidence}


@router.get("/assertions")
def list_assertions(dataset_id: uuid.UUID | None = Query(default=None), user: dict = Depends(require_user)):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_tables(cur, "quality_assertion", "quality_result")
            cur.execute("""SELECT a.id::text, a.dataset_id::text, d.name AS dataset_name, a.name,
                a.assertion_type, a.definition, a.severity, a.schedule, a.enabled, a.created_at,
                latest.status AS latest_status, latest.checked_count, latest.failed_count, latest.evaluated_at
                FROM quality_assertion a JOIN dataset d ON d.id=a.dataset_id
                LEFT JOIN LATERAL (SELECT status, checked_count, failed_count, evaluated_at FROM quality_result r
                    WHERE r.assertion_id=a.id ORDER BY evaluated_at DESC LIMIT 1) latest ON TRUE
                WHERE (%s::uuid IS NULL OR a.dataset_id=%s::uuid) ORDER BY a.created_at DESC""",
                (str(dataset_id) if dataset_id else None, str(dataset_id) if dataset_id else None))
            rows = [dict(row) for row in cur.fetchall()]
    return {"assertions": rows, "count": len(rows)}


@router.post("/assertions", dependencies=[Depends(require_role("owner", "admin", "editor"))])
def create_assertion(request: AssertionInput, user: dict = Depends(require_user)):
    if request.assertion_type == "custom_sql":
        raise HTTPException(status_code=501, detail="Custom SQL assertions are disabled until an approved parameterized, read-only source-query runner and data:preview permission are available.")
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_tables(cur, "quality_assertion")
            cur.execute("SELECT id FROM dataset WHERE id=%s::uuid", (str(request.dataset_id),))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Asset not found")
            cur.execute("""INSERT INTO quality_assertion
                (dataset_id,name,assertion_type,definition,severity,schedule,created_by)
                VALUES (%s::uuid,%s,%s,%s,%s,%s,%s::uuid)
                RETURNING id::text,dataset_id::text,name,assertion_type,definition,severity,schedule,enabled,created_at""",
                (str(request.dataset_id), request.name.strip(), request.assertion_type, Json(request.definition), request.severity, request.schedule, user["id"]))
            result = dict(cur.fetchone())
    return result


@router.post("/assertions/{assertion_id}/evaluate", dependencies=[Depends(require_role("owner", "admin", "editor"))])
def evaluate_assertion(assertion_id: uuid.UUID, user: dict = Depends(require_user)):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_tables(cur, "quality_assertion", "quality_result", "incident", "incident_event", "notification")
            cur.execute("SELECT id::text,dataset_id::text,name,assertion_type,definition,severity FROM quality_assertion WHERE id=%s::uuid AND enabled FOR UPDATE", (str(assertion_id),))
            assertion = cur.fetchone()
            if assertion is None:
                raise HTTPException(status_code=404, detail="Enabled assertion not found")
            result = _result_for_assertion(cur, assertion)
            cur.execute("""INSERT INTO quality_result (assertion_id,status,checked_count,failed_count,evidence,error_code)
                VALUES (%s::uuid,%s,%s,%s,%s,%s) RETURNING id::text,evaluated_at""",
                (assertion["id"], result["status"], result["checked_count"], result["failed_count"], Json(result["evidence"]), "UNSUPPORTED" if result["status"] == "SKIPPED" else None))
            persisted = dict(cur.fetchone())
            if result["status"] == "FAIL":
                dedupe = f"quality:{assertion['id']}"
                cur.execute("SELECT owner_id FROM dataset WHERE id=%s::uuid", (assertion["dataset_id"],))
                owner_row = cur.fetchone()
                owner_id = str(owner_row["owner_id"] or "") if owner_row else ""
                if not re.fullmatch(r"[0-9a-fA-F-]{36}", owner_id):
                    owner_id = ""
                cur.execute("SELECT to_regclass('public.workspace_member') AS relation")
                if not cur.fetchone()["relation"]:
                    owner_id = ""
                elif owner_id:
                    cur.execute("SELECT user_id::text FROM workspace_member WHERE user_id=%s::uuid AND status='active'", (owner_id,))
                    member = cur.fetchone()
                    owner_id = member["user_id"] if member else ""
                cur.execute("""INSERT INTO incident(dataset_id,title,severity,status,dedupe_key,breach_type,detail,assigned_user_id)
                    VALUES (%s::uuid,%s,%s,'DETECTED',%s,'quality',%s,%s::uuid)
                    ON CONFLICT (workspace_id,dedupe_key) WHERE status <> 'RESOLVED' DO NOTHING
                    RETURNING id::text""", (assertion["dataset_id"], f"Quality assertion failed: {assertion['name']}", assertion["severity"], dedupe, Json({"assertion_id": assertion["id"], "result_id": persisted["id"], "evidence": result["evidence"]}), owner_id or None))
                incident = cur.fetchone()
                if incident:
                    cur.execute("INSERT INTO incident_event(incident_id,event_type,actor_user_id,detail) VALUES (%s::uuid,'DETECTED',%s::uuid,%s)", (incident["id"], user["id"], Json({"breach_type": "quality", "result_id": persisted["id"]})))
                    if owner_id:
                        cur.execute("INSERT INTO notification(recipient_user_id,event_type,title,detail,action_path) VALUES (%s::uuid,'QUALITY_FAILURE',%s,%s,%s)", (owner_id, f"Quality assertion failed: {assertion['name']}", Json({"incident_id": incident["id"], "result_id": persisted["id"]}), f"/governance/incidents?id={incident['id']}"))
    return {**persisted, **result, "assertion_id": str(assertion_id)}


@router.get("/assertions/{assertion_id}/results")
def list_assertion_results(assertion_id: uuid.UUID, limit: int = Query(default=50, ge=1, le=200), user: dict = Depends(require_user)):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_tables(cur, "quality_assertion", "quality_result")
            cur.execute("SELECT id FROM quality_assertion WHERE id=%s::uuid", (str(assertion_id),))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Assertion not found")
            cur.execute("SELECT id::text,status,checked_count,failed_count,evidence,error_code,evaluated_at FROM quality_result WHERE assertion_id=%s::uuid ORDER BY evaluated_at DESC LIMIT %s", (str(assertion_id),limit))
            rows = [dict(row) for row in cur.fetchall()]
    return {"results": rows, "count": len(rows)}

