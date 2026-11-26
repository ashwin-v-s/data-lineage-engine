"""Create in-app notifications and deliver their email copies.

The in-app row is written inside the caller's transaction.  Email is sent only
after that transaction commits, so an SMTP outage can never roll back a
governance event or lose the notification.  Delivery uses the same SMTP
settings and branded template as workspace invitations.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit

from psycopg2.extras import Json

from backend.app.db import get_conn, resolve_user_email
from backend.app.services.email_delivery import (
    EmailDeliveryError,
    EmailSettings,
    send_notification_email,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NotificationMessage:
    """The notification fields needed for an email copy after commit."""

    recipient_user_id: str
    event_type: str
    title: str
    detail: dict[str, Any]
    action_path: str | None


def app_action_path(action_path: str | None) -> str | None:
    """Map legacy backend action paths to valid SPA query-string URLs.

    Older notification rows store paths such as
    ``/governance/freshness?asset=...``.  Those paths are not frontend routes;
    opening one falls through to the API/static 404 handler.  The SPA is
    addressable through ``/?view=<view>``, so normalize the known legacy
    shapes without changing already-valid links.
    """
    if not isinstance(action_path, str) or not action_path.strip():
        return action_path
    raw = action_path.strip()
    split = urlsplit(raw)
    params = dict(parse_qsl(split.query, keep_blank_values=True))

    if split.path == "/governance/freshness":
        return f"/?{urlencode({'view': 'freshness', **params})}"
    if split.path == "/governance/incidents":
        return f"/?{urlencode({'view': 'incidents', **params})}"
    if split.path.startswith("/governance/incidents/"):
        params["id"] = split.path.rsplit("/", 1)[-1]
        return f"/?{urlencode({'view': 'incidents', **params})}"
    return raw


def _value(row, key: str, index: int = 0):
    """Read a column from either a RealDictCursor row or a tuple row."""
    if row is None:
        return None
    return row.get(key) if isinstance(row, dict) else row[index]


def create_in_app_notification(
    cur,
    recipient_id: str,
    event_type: str,
    title: str,
    detail: dict[str, Any],
    action_path: str | None,
) -> NotificationMessage | None:
    """Insert the notification and return the payload to email after commit."""
    cur.execute("SELECT to_regclass('public.notification') AS relation")
    if _value(cur.fetchone(), "relation") is None:
        return None
    cur.execute(
        """INSERT INTO notification (recipient_user_id,event_type,title,detail,action_path)
           VALUES (%s::uuid,%s,%s,%s,%s)""",
        (recipient_id, event_type, title, Json(detail), action_path),
    )
    return NotificationMessage(
        recipient_user_id=str(recipient_id),
        event_type=event_type,
        title=title,
        detail=dict(detail),
        action_path=action_path,
    )


def _preference_allows_email(recipient_user_id: str, event_type: str) -> bool:
    """Email is opt-out: only an explicit workspace preference can disable it."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.notification_preference') AS relation")
            if _value(cur.fetchone(), "relation") is None:
                return True
            cur.execute(
                """SELECT email FROM notification_preference
                   WHERE user_id=%s::uuid AND event_type=%s
                   LIMIT 1""",
                (recipient_user_id, event_type),
            )
            row = cur.fetchone()
    return True if row is None else bool(_value(row, "email"))


def dispatch_notification_emails(messages: list[NotificationMessage]) -> None:
    """Email committed notifications, never raising into the request path."""
    messages = [message for message in messages if message is not None]
    if not messages:
        return
    try:
        settings = EmailSettings.from_env()
    except EmailDeliveryError as exc:
        logger.warning("Notification email configuration is invalid: %s", exc)
        return
    if settings is None:
        logger.info("Notification email skipped: SMTP delivery is not configured")
        return

    for message in messages:
        try:
            recipient_email = resolve_user_email(message.recipient_user_id)
            if not recipient_email:
                logger.warning(
                    "Notification email skipped: no auth email for recipient %s",
                    message.recipient_user_id,
                )
                continue
            if not _preference_allows_email(message.recipient_user_id, message.event_type):
                continue
            send_notification_email(
                recipient_email,
                event_type=message.event_type,
                title=message.title,
                action_path=app_action_path(message.action_path),
            )
        except Exception:
            # The notification is already committed. Delivery is best-effort and
            # must not fail the governance request that generated it.
            logger.warning(
                "Could not email %s notification to recipient %s",
                message.event_type,
                message.recipient_user_id,
                exc_info=True,
            )
