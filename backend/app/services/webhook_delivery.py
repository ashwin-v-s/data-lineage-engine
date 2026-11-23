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
import ipaddress
import json
import socket
import time
from typing import Any
from urllib.parse import urlsplit

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


class BlockedDestination(httpx.HTTPError):
    """The webhook URL points at a host we refuse to make requests to."""


def is_internal_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True for addresses that are not routable public destinations.

    Covers loopback, RFC1918/ULA private space, link-local (including the
    169.254.169.254 metadata service), multicast, reserved and unspecified.
    """
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def assert_public_destination(url: str) -> None:
    """Refuse to deliver to a loopback, private or link-local destination.

    The host is resolved here — at delivery time, not only at registration — so
    a DNS record cannot be repointed at an internal address after the webhook
    was created.  Redirects are already disabled, so this is the only hop.
    """
    parsed = urlsplit(url)
    host = parsed.hostname
    if parsed.scheme != "https" or not host:
        raise BlockedDestination("Refusing to deliver: webhook URLs must be https with a host")
    try:
        port = parsed.port or 443
    except ValueError as exc:  # malformed :port
        raise BlockedDestination("Refusing to deliver: webhook URL has an invalid port") from exc
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        raise BlockedDestination(f"Refusing to deliver: host {host!r} did not resolve") from exc
    addresses = {info[4][0].split("%", 1)[0] for info in infos if info[4]}
    if not addresses:
        raise BlockedDestination(f"Refusing to deliver: host {host!r} did not resolve")
    for raw in addresses:
        try:
            address = ipaddress.ip_address(raw)
        except ValueError:
            continue
        if is_internal_address(address):
            raise BlockedDestination(
                f"Refusing to deliver: host {host!r} resolves to a private or loopback address"
            )


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
    assert_public_destination(url)
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
