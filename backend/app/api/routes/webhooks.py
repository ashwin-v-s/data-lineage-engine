"""Workspace webhooks and delivery history (migration 0016).

A webhook is an outbound HTTPS endpoint subscribed to a small, explicit set of
events.  Registration stores the signing secret only as a ``token_crypto``
envelope, and every delivery attempt — including transport failures — is
recorded so the workspace can audit what was sent and what the receiver said.

``POST /webhooks/{id}/test`` performs a real signed POST to the configured URL
and returns the recorded outcome.  It is the same code path production events
use, so a successful test is evidence the endpoint works.
"""
from __future__ import annotations

import ipaddress
import secrets
import uuid
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg2 import Error as PostgresError
from psycopg2.extras import Json
from pydantic import BaseModel, Field, field_validator

from backend.app.api.routes.membership import require_role
from backend.app.auth import require_user
from backend.app.db import get_conn
from backend.app.services.token_crypto import TokenCryptoError, encrypt_token, is_configured
from backend.app.services.webhook_delivery import (
    SUPPORTED_EVENTS,
    deliver,
    is_internal_address,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"], dependencies=[Depends(require_user)])

_UNPROVISIONED_DETAIL = "Webhooks are not provisioned (migration 0016 not applied)"
_CRYPTO_DETAIL = (
    "Webhook signing requires KAIROS_TOKEN_ENCRYPTION_KEY on the API server, "
    "so signing secrets are never stored in plaintext."
)

_WEBHOOK_COLUMNS = """
    id::text, url, description, events, active,
    created_at, last_delivery_at, last_delivery_status, last_delivery_ok
"""


def _table_missing(cur, table: str) -> bool:
    cur.execute("SELECT to_regclass(%s)", (f"public.{table}",))
    row = cur.fetchone()
    return row is None or row[0] is None


class WebhookCreate(BaseModel):
    url: str = Field(min_length=12, max_length=2048)
    description: str | None = Field(default=None, max_length=200)
    events: list[str] = Field(min_length=1, max_length=16)

    @field_validator("url")
    @classmethod
    def _https_only(cls, value: str) -> str:
        url = value.strip()
        if not url.startswith("https://"):
            raise ValueError("Webhook URLs must use https")
        host = (urlsplit(url).hostname or "").strip().lower()
        if not host:
            raise ValueError("Webhook URLs must include a host")
        # Reject literal internal addresses and obviously local names up front.
        # Named hosts are resolved and re-checked at delivery time, where a DNS
        # record cannot be repointed at an internal address.
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            raise ValueError("Webhook URLs must point at a public host")
        try:
            address = ipaddress.ip_address(host.strip("[]"))
        except ValueError:
            return url
        if is_internal_address(address):
            raise ValueError("Webhook URLs must point at a public host")
        return url

    @field_validator("events")
    @classmethod
    def _known_events(cls, value: list[str]) -> list[str]:
        unknown = sorted({event for event in value if event not in SUPPORTED_EVENTS})
        if unknown:
            raise ValueError(f"Unsupported event(s): {', '.join(unknown)}")
        # Preserve the declared order but drop duplicates.
        seen: list[str] = []
        for event in value:
            if event not in seen:
                seen.append(event)
        return seen


def _serialise(row) -> dict:
    return {
        "id": row[0],
        "url": row[1],
        "description": row[2],
        "events": list(row[3] or []),
        "active": row[4],
        "created_at": row[5].isoformat() if row[5] else None,
        "last_delivery_at": row[6].isoformat() if row[6] else None,
        "last_delivery_status": row[7],
        "last_delivery_ok": row[8],
    }


@router.get("")
def list_webhooks():
    with get_conn() as conn:
        with conn.cursor() as cur:
            if _table_missing(cur, "workspace_webhook"):
                raise HTTPException(status_code=503, detail=_UNPROVISIONED_DETAIL)
            cur.execute(
                f"""
                SELECT {_WEBHOOK_COLUMNS}
                FROM workspace_webhook
                WHERE workspace_id = current_setting('kairos.workspace_id', true)::uuid
                ORDER BY created_at DESC
                """
            )
            rows = cur.fetchall()
    return {"ok": True, "webhooks": [_serialise(r) for r in rows], "supported_events": list(SUPPORTED_EVENTS)}


@router.post("", status_code=201, dependencies=[Depends(require_role("owner", "admin"))])
def create_webhook(body: WebhookCreate, user: dict = Depends(require_user)):
    if not is_configured():
        raise HTTPException(status_code=503, detail=_CRYPTO_DETAIL)
    # A distinct signing secret per endpoint keeps one compromised receiver from
    # forging deliveries to another.
    signing_secret = f"whsec_{secrets.token_urlsafe(24)}"
    try:
        ciphertext = encrypt_token(signing_secret)
    except TokenCryptoError as exc:
        raise HTTPException(status_code=503, detail=_CRYPTO_DETAIL) from exc
    actor_id = user.get("id") or user.get("sub")
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                if _table_missing(cur, "workspace_webhook"):
                    raise HTTPException(status_code=503, detail=_UNPROVISIONED_DETAIL)
                cur.execute(
                    f"""
                    INSERT INTO workspace_webhook
                        (workspace_id, created_by, url, description, events, signing_secret_ciphertext)
                    VALUES (
                        current_setting('kairos.workspace_id', true)::uuid,
                        %s::uuid, %s, %s, %s, %s
                    )
                    RETURNING {_WEBHOOK_COLUMNS}
                    """,
                    (str(actor_id), body.url, body.description, body.events, ciphertext),
                )
                row = cur.fetchone()
    except PostgresError as exc:
        if getattr(exc, "pgcode", None) == "23505":
            raise HTTPException(status_code=409, detail="A webhook with that URL already exists") from exc
        raise
    return {
        "ok": True,
        "webhook": _serialise(row),
        # Shown once; the receiver uses it to verify X-Kairos-Signature.
        "signing_secret": signing_secret,
    }


@router.delete("/{webhook_id}")
def delete_webhook(webhook_id: uuid.UUID, user: dict = Depends(require_role("owner", "admin"))):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if _table_missing(cur, "workspace_webhook"):
                raise HTTPException(status_code=503, detail=_UNPROVISIONED_DETAIL)
            cur.execute(
                """
                DELETE FROM workspace_webhook
                 WHERE id = %s::uuid
                   AND workspace_id = current_setting('kairos.workspace_id', true)::uuid
                RETURNING id::text
                """,
                (str(webhook_id),),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return {"ok": True, "id": row[0], "deleted": True}


@router.post("/{webhook_id}/test")
def test_webhook(webhook_id: uuid.UUID, user: dict = Depends(require_role("owner", "admin"))):
    """Deliver a real ``test.ping`` and record the outcome."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            if _table_missing(cur, "workspace_webhook"):
                raise HTTPException(status_code=503, detail=_UNPROVISIONED_DETAIL)
            cur.execute(
                """
                SELECT id::text, url, workspace_id::text, signing_secret_ciphertext, active
                FROM workspace_webhook
                WHERE id = %s::uuid
                  AND workspace_id = current_setting('kairos.workspace_id', true)::uuid
                """,
                (str(webhook_id),),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Webhook not found")
            webhook = {
                "id": row[0],
                "url": row[1],
                "workspace_id": row[2],
                "signing_secret_ciphertext": row[3],
                "active": row[4],
            }
            if not webhook["active"]:
                raise HTTPException(status_code=409, detail="Webhook is inactive")

            outcome = deliver(webhook, "test.ping", {"message": "Kairos webhook delivery test"})

            cur.execute(
                """
                INSERT INTO workspace_webhook_delivery
                    (webhook_id, workspace_id, event_type, payload, response_status,
                     response_excerpt, ok, error, duration_ms)
                VALUES (
                    %s::uuid, current_setting('kairos.workspace_id', true)::uuid, %s, %s,
                    %s, %s, %s, %s, %s
                )
                RETURNING id::text, created_at
                """,
                (
                    webhook["id"], outcome["event_type"], Json(outcome["payload"]),
                    outcome["response_status"], outcome["response_excerpt"], outcome["ok"],
                    outcome["error"], outcome["duration_ms"],
                ),
            )
            delivery_row = cur.fetchone()
            cur.execute(
                """
                UPDATE workspace_webhook
                   SET last_delivery_at = now(), last_delivery_status = %s,
                       last_delivery_ok = %s, updated_at = now()
                 WHERE id = %s::uuid
                """,
                (outcome["response_status"], outcome["ok"], webhook["id"]),
            )
    return {
        "ok": outcome["ok"],
        "delivery": {
            "id": delivery_row[0],
            "webhook_id": webhook["id"],
            "event_type": outcome["event_type"],
            "response_status": outcome["response_status"],
            "response_excerpt": outcome["response_excerpt"],
            "ok": outcome["ok"],
            "error": outcome["error"],
            "duration_ms": outcome["duration_ms"],
            "signed": outcome["signed"],
            "created_at": delivery_row[1].isoformat() if delivery_row[1] else None,
        },
    }


@router.get("/{webhook_id}/deliveries")
def list_deliveries(
    webhook_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    outcome: Literal["all", "ok", "failed"] = Query(default="all"),
):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if _table_missing(cur, "workspace_webhook_delivery"):
                raise HTTPException(status_code=503, detail=_UNPROVISIONED_DETAIL)
            condition = ""
            params: list = [str(webhook_id), limit]
            if outcome == "ok":
                condition = " AND ok"
            elif outcome == "failed":
                condition = " AND NOT ok"
            cur.execute(
                f"""
                SELECT id::text, event_type, response_status, response_excerpt, ok, error,
                       duration_ms, created_at
                FROM workspace_webhook_delivery
                WHERE webhook_id = %s::uuid
                  AND workspace_id = current_setting('kairos.workspace_id', true)::uuid{condition}
                ORDER BY created_at DESC
                LIMIT %s
                """,
                tuple(params),
            )
            rows = cur.fetchall()
    return {
        "ok": True,
        "deliveries": [
            {
                "id": r[0],
                "event_type": r[1],
                "response_status": r[2],
                "response_excerpt": r[3],
                "ok": r[4],
                "error": r[5],
                "duration_ms": r[6],
                "created_at": r[7].isoformat() if r[7] else None,
            }
            for r in rows
        ],
    }
