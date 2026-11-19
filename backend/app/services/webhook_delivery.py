"""Outbound webhook delivery with HMAC-SHA256 signatures.

Delivery is a single bounded POST.  Every attempt — success, non-2xx or
transport failure — produces one ``workspace_webhook_delivery`` row so the
workspace has an auditable history rather than a fire-and-forget log line.
Signing secrets live only as ``token_crypto`` envelopes and are decrypted in
memory for the duration of the request.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

import httpx

from backend.app.services.token_crypto import TokenCryptoError, decrypt_token

# Events a workspace can subscribe to today.  Kept small and explicit: an
# unknown event name is a configuration mistake, not something to store.
SUPPORTED_EVENTS: tuple[str, ...] = (
    "test.ping",
    "catalog.asset.updated",
    "catalog.asset.removed",
    "freshness.breach",
    "quality.failed",
    "incident.opened",
    "incident.resolved",
)

DELIVERY_TIMEOUT_SECONDS = 10.0
RESPONSE_EXCERPT_CHARS = 400


def sign_payload(secret: str, body: bytes) -> str:
    """Return the ``sha256=<hex>`` signature header value for a payload."""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def build_payload(webhook: dict[str, Any], event_type: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the JSON body sent to the receiver.

    Keys are sorted at serialisation time so a receiver can verify the
    signature against exactly the bytes it received.
    """
    return {
        "event": event_type,
        "workspace_id": webhook.get("workspace_id"),
        "webhook_id": webhook.get("id"),
        "sent_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "data": data or {},
    }


def serialise(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _signing_secret(webhook: dict[str, Any]) -> str | None:
    ciphertext = webhook.get("signing_secret_ciphertext")
    if not ciphertext:
        return None
    try:
        return decrypt_token(ciphertext)
    except TokenCryptoError:
        # A key rotation that dropped the old version must not crash delivery;
        # the event is still sent, just unsigned, and the row records it.
        return None


def _post(url: str, body: bytes, headers: dict[str, str]) -> httpx.Response:
    """Single seam for tests: one POST with a bounded timeout, no retries."""
    with httpx.Client(timeout=DELIVERY_TIMEOUT_SECONDS, follow_redirects=False) as client:
        return client.post(url, content=body, headers=headers)


def deliver(webhook: dict[str, Any], event_type: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    """POST one event to a webhook and return the recorded outcome."""
    payload = build_payload(webhook, event_type, data)
    body = serialise(payload)
    secret = _signing_secret(webhook)
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Kairos-Webhooks/1.0",
        "X-Kairos-Event": event_type,
        "X-Kairos-Webhook-Id": str(webhook.get("id")),
    }
    if secret:
        headers["X-Kairos-Signature"] = sign_payload(secret, body)

    started = time.monotonic()
    status_code: int | None = None
    excerpt: str | None = None
    error: str | None = None
    ok = False
    try:
        response = _post(webhook["url"], body, headers)
        status_code = response.status_code
        ok = 200 <= status_code < 300
        text = (response.text or "").strip()
        if text:
            excerpt = text[:RESPONSE_EXCERPT_CHARS]
        if not ok:
            error = f"Receiver returned HTTP {status_code}"
    except httpx.HTTPError as exc:
        error = f"{type(exc).__name__}: {exc}"[:500]
    duration_ms = int((time.monotonic() - started) * 1000)

    return {
        "event_type": event_type,
        "payload": payload,
        "response_status": status_code,
        "response_excerpt": excerpt,
        "ok": ok,
        "error": error,
        "duration_ms": duration_ms,
        "signed": secret is not None,
    }
