"""Workspace stewardship requests (migration 0017).

A request is either ``access`` (a member asks for access to a catalog asset) or
``glossary`` (a member proposes a term).  Any authenticated member can raise
one; only an owner or admin can resolve it.  Approval records a decision for
the requester — it does not grant source-system access or publish a term.
"""
from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.app.api.routes.membership import require_role
from backend.app.auth import require_user
from backend.app.db import get_conn

router = APIRouter(prefix="/stewardship", tags=["stewardship"], dependencies=[Depends(require_user)])

_UNPROVISIONED_DETAIL = "Stewardship requests are not provisioned (migration 0017 not applied)"

_REQUEST_COLUMNS = """
    id::text, kind, dataset_id::text, asset_label, title, detail,
    requested_by::text, requested_by_label, status, resolution_note,
    resolved_by::text, resolved_at, created_at, updated_at
"""


def _table_missing(cur, table: str) -> bool:
    cur.execute("SELECT to_regclass(%s)", (f"public.{table}",))
    row = cur.fetchone()
    return row is None or row[0] is None


class RequestCreate(BaseModel):
    kind: Literal["access", "glossary"]
    detail: str = Field(min_length=1, max_length=4000)
    dataset_id: uuid.UUID | None = None
    asset_label: str | None = Field(default=None, max_length=1024)
    title: str | None = Field(default=None, max_length=160)

    @field_validator("detail")
    @classmethod
    def _detail_present(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("Describe the request before submitting it")
        return text

    @field_validator("asset_label", "title")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None

    @model_validator(mode="after")
    def _target_present(self):
        if self.kind == "access" and not self.asset_label:
            raise ValueError("An access request needs the asset it is for")
        if self.kind == "glossary" and not self.title:
            raise ValueError("A glossary proposal needs a term name")
        return self


class Resolution(BaseModel):
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("note")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None


def _serialise(row) -> dict:
    return {
        "id": row[0],
        "kind": row[1],
        "dataset_id": row[2],
        "asset_label": row[3],
        "title": row[4],
        "detail": row[5],
        "requested_by": row[6],
        "requested_by_label": row[7],
        "status": row[8],
        "resolution_note": row[9],
        "resolved_by": row[10],
        "resolved_at": row[11].isoformat() if row[11] else None,
        "created_at": row[12].isoformat() if row[12] else None,
        "updated_at": row[13].isoformat() if row[13] else None,
    }


@router.get("/requests")
def list_requests(
    status: Literal["all", "pending", "approved", "rejected"] = Query(default="all"),
    kind: Literal["all", "access", "glossary"] = Query(default="all"),
    limit: int = Query(default=100, ge=1, le=200),
):
    conditions: list[str] = []
    params: list = []
    if status != "all":
        conditions.append("AND status = %s")
        params.append(status.upper())
    if kind != "all":
        conditions.append("AND kind = %s")
        params.append(kind)
    where = (" ".join(conditions)) if conditions else ""
    params.append(limit)
    with get_conn() as conn:
        with conn.cursor() as cur:
            if _table_missing(cur, "stewardship_request"):
                raise HTTPException(status_code=503, detail=_UNPROVISIONED_DETAIL)
            cur.execute(
                f"""
                SELECT {_REQUEST_COLUMNS}
                FROM stewardship_request
                WHERE workspace_id = current_setting('kairos.workspace_id', true)::uuid
                {where}
                ORDER BY (status = 'PENDING') DESC, created_at DESC
                LIMIT %s
                """,
                tuple(params),
            )
            rows = cur.fetchall()
    requests = [_serialise(r) for r in rows]
    counts = {"PENDING": 0, "APPROVED": 0, "REJECTED": 0}
    for item in requests:
        if item["status"] in counts:
            counts[item["status"]] += 1
    return {"ok": True, "requests": requests, "counts": counts, "count": len(requests)}


@router.post("/requests", status_code=201)
def create_request(body: RequestCreate, user: dict = Depends(require_user)):
    actor_id = user.get("id") or user.get("sub")
    if not actor_id or str(actor_id).startswith("api-key:"):
        # Machine credentials act for a workspace, not as a person who can raise
        # or be granted a stewardship request.
        raise HTTPException(status_code=403, detail="Stewardship requests require a signed-in member")
    with get_conn() as conn:
        with conn.cursor() as cur:
            if _table_missing(cur, "stewardship_request"):
                raise HTTPException(status_code=503, detail=_UNPROVISIONED_DETAIL)
            cur.execute(
                f"""
                INSERT INTO stewardship_request
                    (workspace_id, kind, dataset_id, asset_label, title, detail,
                     requested_by, requested_by_label)
                VALUES (
                    current_setting('kairos.workspace_id', true)::uuid,
                    %s, %s::uuid, %s, %s, %s, %s::uuid, %s
                )
                RETURNING {_REQUEST_COLUMNS}
                """,
                (
                    body.kind,
                    str(body.dataset_id) if body.dataset_id else None,
                    body.asset_label,
                    body.title,
                    body.detail,
                    str(actor_id),
                    user.get("email"),
                ),
            )
            row = cur.fetchone()
    return {"ok": True, "request": _serialise(row)}


def _resolve(request_id: uuid.UUID, status: Literal["APPROVED", "REJECTED"], note: str | None, user: dict) -> dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            if _table_missing(cur, "stewardship_request"):
                raise HTTPException(status_code=503, detail=_UNPROVISIONED_DETAIL)
            cur.execute(
                """
                SELECT status FROM stewardship_request
                 WHERE id = %s::uuid
                   AND workspace_id = current_setting('kairos.workspace_id', true)::uuid
                """,
                (str(request_id),),
            )
            existing = cur.fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="Stewardship request not found")
            if existing[0] != "PENDING":
                raise HTTPException(status_code=409, detail="This request has already been resolved")
            cur.execute(
                f"""
                UPDATE stewardship_request
                   SET status = %s, resolution_note = %s, resolved_by = %s::uuid,
                       resolved_at = now(), updated_at = now()
                 WHERE id = %s::uuid
                   AND workspace_id = current_setting('kairos.workspace_id', true)::uuid
                RETURNING {_REQUEST_COLUMNS}
                """,
                (status, note, str(user.get("id") or user.get("sub")), str(request_id)),
            )
            row = cur.fetchone()
    return {"ok": True, "request": _serialise(row)}


@router.post("/requests/{request_id}/approve")
def approve_request(
    request_id: uuid.UUID,
    body: Resolution | None = None,
    user: dict = Depends(require_role("owner", "admin")),
):
    return _resolve(request_id, "APPROVED", body.note if body else None, user)


@router.post("/requests/{request_id}/reject")
def reject_request(
    request_id: uuid.UUID,
    body: Resolution | None = None,
    user: dict = Depends(require_role("owner", "admin")),
):
    return _resolve(request_id, "REJECTED", body.note if body else None, user)
