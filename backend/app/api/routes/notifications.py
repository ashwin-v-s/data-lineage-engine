"""Authenticated, workspace-scoped in-app notification center."""
from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, ConfigDict

from backend.app.auth import require_user
from backend.app.db import get_conn

router = APIRouter(prefix="/notifications", tags=["notifications"], dependencies=[Depends(require_user)])
EVENT_TYPES = ("FRESHNESS_BREACH", "QUALITY_FAILURE", "INCIDENT_CREATED", "SYNC_FAILURE", "CREDENTIAL_EXPIRY", "LINEAGE_CHANGE", "PII_CHANGE")


def _require_table(cur):
    cur.execute("SELECT to_regclass('public.notification') AS relation")
    if cur.fetchone()["relation"] is None:
        raise HTTPException(status_code=503, detail="Notification storage is unavailable; verify migration 0011_m4_governance.sql is applied.")


@router.get("")
def list_notifications(unread_only: bool = False, limit: int = Query(default=50, ge=1, le=100), user: dict = Depends(require_user)):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_table(cur)
            cur.execute("SELECT id::text,event_type,title,detail,action_path,read_at,created_at FROM notification WHERE recipient_user_id=%s::uuid AND (%s=false OR read_at IS NULL) ORDER BY created_at DESC LIMIT %s", (user["id"],unread_only,limit))
            rows = [dict(row) for row in cur.fetchall()]
            cur.execute("SELECT count(*)::int AS unread_count FROM notification WHERE recipient_user_id=%s::uuid AND read_at IS NULL", (user["id"],))
            unread_count = cur.fetchone()["unread_count"]
    return {"notifications": rows, "count": len(rows), "unread_count": unread_count}


class MarkReadInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    notification_ids: list[uuid.UUID]


@router.post("/read")
def mark_read(body: MarkReadInput, user: dict = Depends(require_user)):
    if not body.notification_ids or len(body.notification_ids) > 100:
        raise HTTPException(status_code=422, detail="Provide between 1 and 100 notification IDs")
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_table(cur)
            cur.execute("UPDATE notification SET read_at=coalesce(read_at,now()) WHERE recipient_user_id=%s::uuid AND id=ANY(%s::uuid[])", (user["id"],[str(value) for value in body.notification_ids]))
            updated = cur.rowcount
    return {"updated": updated}


@router.post("/read-all")
def mark_all_read(user: dict = Depends(require_user)):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_table(cur)
            cur.execute("UPDATE notification SET read_at=now() WHERE recipient_user_id=%s::uuid AND read_at IS NULL", (user["id"],))
            updated = cur.rowcount
    return {"updated": updated}


class PreferenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_type: str
    in_app: bool = True
    email: bool = False


@router.get("/preferences")
def get_preferences(user: dict = Depends(require_user)):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_table(cur)
            cur.execute("SELECT to_regclass('public.notification_preference') AS relation")
            if not cur.fetchone()["relation"]:
                raise HTTPException(status_code=503, detail="Notification preferences are unavailable until migration 0011 is approved and applied.")
            cur.execute("SELECT event_type,in_app,email FROM notification_preference WHERE user_id=%s::uuid ORDER BY event_type", (user["id"],))
            rows = [dict(row) for row in cur.fetchall()]
    return {"preferences": rows, "supported_event_types": list(EVENT_TYPES)}


@router.put("/preferences")
def set_preference(body: PreferenceInput, user: dict = Depends(require_user)):
    if body.event_type not in EVENT_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported notification event type")
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_table(cur)
            cur.execute("SELECT to_regclass('public.notification_preference') AS relation")
            if not cur.fetchone()["relation"]:
                raise HTTPException(status_code=503, detail="Notification preferences are unavailable until migration 0011 is approved and applied.")
            cur.execute("INSERT INTO notification_preference(user_id,event_type,in_app,email) VALUES (%s::uuid,%s,%s,%s) ON CONFLICT(workspace_id,user_id,event_type) DO UPDATE SET in_app=EXCLUDED.in_app,email=EXCLUDED.email,updated_at=now() RETURNING event_type,in_app,email,updated_at", (user["id"],body.event_type,body.in_app,body.email))
            row = dict(cur.fetchone())
    return row
