"""Trust and collaboration: certification, discussions, engagement and scorecard.

Endpoints
─────────
  GET    /api/v1/trust/overview                              adoption summary
  GET    /api/v1/trust/certifications                        certification register
  PUT    /api/v1/trust/assets/{asset_id}/certification       certify / re-certify
  DELETE /api/v1/trust/assets/{asset_id}/certification       revoke certification
  GET    /api/v1/trust/assets/{asset_id}/discussion          threads and replies
  POST   /api/v1/trust/assets/{asset_id}/discussion          open a thread or reply
  POST   /api/v1/trust/discussion/{comment_id}/resolve       resolve a thread root

Semantics
─────────
Certification is a steward endorsement stored as a row; expiry is evaluated at
read time (CERTIFIED / EXPIRING / EXPIRED) and never persisted as a status that
could drift. Discussions are threaded: only a root can be resolved, and
resolving it resolves the question, not each reply individually. Engagement is
a workspace-level open counter that stores no user identity — per-user history
remains private in ``asset_view``.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.api.routes.membership import require_role
from backend.app.auth import require_user
from backend.app.db import get_conn
from backend.app.services.quality_scorecard import build_scorecard

router = APIRouter(prefix="/trust", tags=["trust"], dependencies=[Depends(require_user)])

WRITE = [Depends(require_role("owner", "admin", "editor"))]

_UNPROVISIONED_DETAIL = (
    "Trust storage is not provisioned (migration 0019 not applied). "
    "Apply backend/migrations/0019_trust_collaboration.sql and restart the API."
)

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

_TS = "to_char({col} AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\"')"

_CERTIFICATION_COLUMNS = f"""
    c.id::text                                  AS id,
    c.dataset_id::text                          AS dataset_id,
    d.name                                      AS dataset_name,
    d.asset_type                                AS asset_type,
    concat_ws('.', NULLIF(d.database_name, ''), NULLIF(d.schema_name, ''), d.name) AS qualified_name,
    c.note                                      AS note,
    c.certified_by::text                        AS certified_by,
    c.certified_by_label                        AS certified_by_label,
    {_TS.format(col='c.expires_at')}            AS expires_at,
    {_TS.format(col='c.created_at')}            AS created_at,
    {_TS.format(col='c.updated_at')}            AS updated_at,
    CASE
        WHEN c.expires_at IS NOT NULL AND c.expires_at <= now() THEN 'EXPIRED'
        WHEN c.expires_at IS NOT NULL AND c.expires_at <= now() + interval '30 days' THEN 'EXPIRING'
        ELSE 'CERTIFIED'
    END                                         AS state
"""

_DISCUSSION_COLUMNS = f"""
    c.id::text                                  AS id,
    c.dataset_id::text                          AS dataset_id,
    c.parent_id::text                           AS parent_id,
    c.author_id::text                           AS author_id,
    c.author_label                              AS author_label,
    c.body                                      AS body,
    {_TS.format(col='c.resolved_at')}           AS resolved_at,
    c.resolved_by::text                         AS resolved_by,
    {_TS.format(col='c.created_at')}            AS created_at
"""


class CertificationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str | None = Field(default=None, max_length=1000)
    expires_at: datetime | None = None

    @field_validator("note")
    @classmethod
    def _strip_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None


class DiscussionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=4000)
    parent_id: uuid.UUID | None = None

    @field_validator("body")
    @classmethod
    def _strip_body(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("Write a comment before posting it")
        return text


def _require_trust(cur, *tables: str) -> None:
    """Fail closed until migration 0019 is installed."""
    missing: list[str] = []
    for table in tables:
        cur.execute("SELECT to_regclass(%s) AS relation", (f"public.{table}",))
        row = cur.fetchone()
        relation = row["relation"] if isinstance(row, dict) else (row[0] if row else None)
        if relation is None:
            missing.append(table)
    if missing:
        raise HTTPException(
            status_code=503,
            detail=f"Trust storage is unavailable (missing: {', '.join(missing)}). Apply migration 0019.",
        )


def _resolve_dataset(cur, asset_id: str) -> dict:
    """Resolve an asset UUID or dataset name inside the current workspace."""
    if _UUID_RE.match(asset_id):
        cur.execute("SELECT id::text AS id, name FROM dataset WHERE id = %s::uuid LIMIT 1", (asset_id,))
        row = cur.fetchone()
        if row:
            return dict(row)
    cur.execute(
        """
        SELECT id::text AS id, name FROM dataset
        WHERE lower(name) = lower(%s)
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (asset_id,),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found.")
    return dict(row)


def _actor_id(user: dict) -> str:
    actor = user.get("id") or user.get("sub")
    if not actor or str(actor).startswith("api-key:"):
        raise HTTPException(status_code=403, detail="Certification and discussion require a signed-in member")
    return str(actor)


@router.get("/overview")
def trust_overview(days: int = Query(default=30, ge=1, le=365), user: dict = Depends(require_user)):
    """Adoption, trust and quality snapshot for the trust center."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_trust(cur, "asset_certification", "asset_discussion", "asset_engagement")

            cur.execute(
                """
                SELECT count(*)::int AS total,
                       count(*) FILTER (WHERE expires_at IS NOT NULL AND expires_at <= now())::int AS expired,
                       count(*) FILTER (
                           WHERE expires_at IS NOT NULL
                             AND expires_at > now()
                             AND expires_at <= now() + interval '30 days'
                       )::int AS expiring
                FROM asset_certification
                """
            )
            certification = dict(cur.fetchone())

            cur.execute(
                "SELECT count(*)::int AS total, count(*) FILTER (WHERE owner_name IS NOT NULL AND btrim(owner_name) <> '')::int AS owned FROM dataset"
            )
            assets = dict(cur.fetchone())

            cur.execute(
                """
                SELECT count(*) FILTER (WHERE parent_id IS NULL)::int AS threads,
                       count(*) FILTER (WHERE parent_id IS NULL AND resolved_at IS NULL)::int AS open_threads,
                       count(*)::int AS comments
                FROM asset_discussion
                """
            )
            discussion = dict(cur.fetchone())

            cur.execute(
                """
                SELECT d.id::text AS asset_id,
                       d.name,
                       d.asset_type,
                       concat_ws('.', NULLIF(d.database_name, ''), NULLIF(d.schema_name, ''), d.name) AS qualified_name,
                       e.view_count,
                       to_char(e.last_viewed_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"') AS last_viewed_at
                FROM   asset_engagement e
                JOIN   dataset d ON d.id = e.dataset_id
                ORDER  BY e.view_count DESC, e.last_viewed_at DESC
                LIMIT  5
                """
            )
            trending = [dict(row) for row in cur.fetchall()]

            scorecard = build_scorecard(cur, days=days)

    certified = certification["total"]
    total_assets = assets["total"]
    return {
        "certification": {
            "certified": certified - certification["expired"],
            "expiring_soon": certification["expiring"],
            "expired": certification["expired"],
            "uncertified": max(0, total_assets - certified),
            "coverage": round(certified / total_assets, 4) if total_assets else None,
        },
        "ownership": {
            "assets": total_assets,
            "with_owner": assets["owned"],
            "coverage": round(assets["owned"] / total_assets, 4) if total_assets else None,
        },
        "discussion": {
            "threads": discussion["threads"],
            "open_threads": discussion["open_threads"],
            "resolved_threads": discussion["threads"] - discussion["open_threads"],
            "comments": discussion["comments"],
        },
        "trending": trending,
        "trending_basis": "Recorded asset opens by signed-in workspace members. Aggregated without user identity.",
        "quality": scorecard,
    }


@router.get("/certifications")
def list_certifications(
    state: Literal["all", "certified", "expiring", "expired"] = Query(default="all"),
    limit: int = Query(default=200, ge=1, le=500),
    user: dict = Depends(require_user),
):
    """List certifications with a read-time CERTIFIED / EXPIRING / EXPIRED state."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_trust(cur, "asset_certification")
            cur.execute(
                f"""
                SELECT {_CERTIFICATION_COLUMNS}
                FROM   asset_certification c
                JOIN   dataset d ON d.id = c.dataset_id
                ORDER  BY c.created_at DESC
                LIMIT  %s
                """,
                (limit,),
            )
            rows = [dict(row) for row in cur.fetchall()]

    if state != "all":
        wanted = state.upper()
        rows = [row for row in rows if row["state"] == wanted]

    counts = {"CERTIFIED": 0, "EXPIRING": 0, "EXPIRED": 0}
    for row in rows:
        if row["state"] in counts:
            counts[row["state"]] += 1
    return {"certifications": rows, "counts": counts, "count": len(rows)}


@router.put("/assets/{asset_id}/certification", dependencies=WRITE)
def certify_asset(asset_id: str, body: CertificationInput, user: dict = Depends(require_user)):
    """Certify or re-certify one asset. Idempotent per asset."""
    actor = _actor_id(user)
    expires_at = body.expires_at
    if expires_at is not None:
        if expires_at.tzinfo is None:
            raise HTTPException(status_code=422, detail="expires_at must include a timezone")
        expires_at = expires_at.astimezone(timezone.utc)
        # Guard against an accidental year-9999 value; 10 years is ample.
        if expires_at.year > datetime.now(timezone.utc).year + 10:
            raise HTTPException(status_code=422, detail="expires_at is unreasonably far in the future")

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_trust(cur, "asset_certification")
            dataset = _resolve_dataset(cur, asset_id)
            cur.execute(
                """
                INSERT INTO asset_certification (dataset_id, note, certified_by, certified_by_label, expires_at)
                VALUES (%s::uuid, %s, %s::uuid, %s, %s)
                ON CONFLICT (workspace_id, dataset_id) DO UPDATE
                    SET note = EXCLUDED.note,
                        certified_by = EXCLUDED.certified_by,
                        certified_by_label = EXCLUDED.certified_by_label,
                        expires_at = EXCLUDED.expires_at,
                        updated_at = now()
                RETURNING id::text
                """,
                (dataset["id"], body.note, actor, user.get("email"), expires_at),
            )
            certification_id = cur.fetchone()["id"]
            cur.execute(
                f"""
                SELECT {_CERTIFICATION_COLUMNS}
                FROM   asset_certification c
                JOIN   dataset d ON d.id = c.dataset_id
                WHERE  c.id = %s::uuid
                """,
                (certification_id,),
            )
            row = dict(cur.fetchone())
    return {"ok": True, "certification": row}


@router.delete("/assets/{asset_id}/certification", dependencies=WRITE)
def revoke_certification(asset_id: str, user: dict = Depends(require_user)):
    """Revoke one asset's certification. A second call is a 404, not a no-op claim."""
    _actor_id(user)
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_trust(cur, "asset_certification")
            dataset = _resolve_dataset(cur, asset_id)
            cur.execute(
                "DELETE FROM asset_certification WHERE dataset_id = %s::uuid RETURNING id::text",
                (dataset["id"],),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="This asset is not certified")
    return {"ok": True, "asset_id": dataset["id"], "revoked": True}


@router.get("/assets/{asset_id}/discussion")
def list_discussion(asset_id: str, user: dict = Depends(require_user)):
    """Return every stored thread and reply for one asset, oldest first."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_trust(cur, "asset_discussion")
            dataset = _resolve_dataset(cur, asset_id)
            cur.execute(
                f"""
                SELECT {_DISCUSSION_COLUMNS}
                FROM   asset_discussion c
                WHERE  c.dataset_id = %s::uuid
                ORDER  BY c.created_at ASC
                LIMIT  500
                """,
                (dataset["id"],),
            )
            comments = [dict(row) for row in cur.fetchall()]

    threads = [row for row in comments if row["parent_id"] is None]
    return {
        "asset_id": dataset["id"],
        "asset_name": dataset["name"],
        "comments": comments,
        "count": len(comments),
        "threads": len(threads),
        "open_threads": len([row for row in threads if row["resolved_at"] is None]),
        "truncated": len(comments) >= 500,
    }


@router.post("/assets/{asset_id}/discussion", status_code=201)
def create_discussion(asset_id: str, body: DiscussionInput, user: dict = Depends(require_user)):
    """Open a thread, or reply to an existing thread root."""
    actor = _actor_id(user)
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_trust(cur, "asset_discussion")
            dataset = _resolve_dataset(cur, asset_id)
            parent_id = str(body.parent_id) if body.parent_id else None
            if parent_id:
                cur.execute(
                    "SELECT id::text, parent_id::text FROM asset_discussion WHERE id = %s::uuid AND dataset_id = %s::uuid",
                    (parent_id, dataset["id"]),
                )
                parent = cur.fetchone()
                if not parent:
                    raise HTTPException(status_code=404, detail="Discussion thread not found for this asset")
                if parent["parent_id"] is not None:
                    raise HTTPException(status_code=422, detail="Replies attach to a thread root, not to another reply")
            cur.execute(
                f"""
                INSERT INTO asset_discussion AS c (dataset_id, parent_id, author_id, author_label, body)
                VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s)
                RETURNING {_DISCUSSION_COLUMNS}
                """,
                (dataset["id"], parent_id, actor, user.get("email"), body.body),
            )
            row = dict(cur.fetchone())
    return {"ok": True, "comment": row}


@router.post("/discussion/{comment_id}/resolve", dependencies=WRITE)
def resolve_discussion(comment_id: uuid.UUID, user: dict = Depends(require_user)):
    """Resolve a thread root. Replies cannot be resolved individually."""
    actor = _actor_id(user)
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _require_trust(cur, "asset_discussion")
            cur.execute(
                "SELECT id::text, parent_id::text, resolved_at FROM asset_discussion WHERE id = %s::uuid FOR UPDATE",
                (str(comment_id),),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Discussion comment not found")
            if row["parent_id"] is not None:
                raise HTTPException(status_code=422, detail="Only a discussion thread can be resolved")
            if row["resolved_at"] is not None:
                raise HTTPException(status_code=409, detail="This thread is already resolved")
            cur.execute(
                f"""
                UPDATE asset_discussion AS c
                   SET resolved_at = now(), resolved_by = %s::uuid
                 WHERE c.id = %s::uuid
                RETURNING {_DISCUSSION_COLUMNS}
                """,
                (actor, str(comment_id)),
            )
            resolved = dict(cur.fetchone())
    return {"ok": True, "comment": resolved}
