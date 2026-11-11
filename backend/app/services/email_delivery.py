"""SMTP delivery for Kairos account and workspace invitation messages."""
from __future__ import annotations

import os
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr
from html import escape
from urllib.parse import quote


class EmailDeliveryError(RuntimeError):
    """Email could not be delivered using the configured SMTP service."""


@dataclass(frozen=True)
class EmailSettings:
    host: str
    port: int
    username: str
    password: str
    sender: str
    app_name: str
    security: str
    public_app_url: str

    @staticmethod
    def _setting(primary: str, legacy: str, default: str = "") -> str:
        """Read deployment-standard SMTP names, retaining old Kairos aliases."""
        return os.getenv(primary) or os.getenv(legacy) or default

    @classmethod
    def from_env(cls) -> "EmailSettings | None":
        host = cls._setting("SMTP_HOST", "KAIROS_EMAIL_HOST").strip()
        username = cls._setting("SMTP_USER", "KAIROS_EMAIL_USERNAME").strip()
        password = cls._setting("SMTP_PASSWORD", "KAIROS_EMAIL_PASSWORD")
        sender = cls._setting("SMTP_FROM", "KAIROS_EMAIL_FROM").strip()
        app_name = os.getenv("SMTP_APP_NAME", "Kairos").strip() or "Kairos"
        public_app_url = (os.getenv("KAIROS_PUBLIC_APP_URL") or "").strip().rstrip("/")
        if not all((host, username, password, sender, public_app_url)):
            return None
        try:
            port = int(cls._setting("SMTP_PORT", "KAIROS_EMAIL_PORT", "587"))
        except ValueError as exc:
            raise EmailDeliveryError("KAIROS_EMAIL_PORT must be a valid port number") from exc
        security = (os.getenv("KAIROS_EMAIL_SECURITY") or ("ssl" if port == 465 else "starttls")).strip().lower()
        if security not in {"ssl", "starttls"}:
            raise EmailDeliveryError("KAIROS_EMAIL_SECURITY must be 'ssl' or 'starttls'")
        if not public_app_url.startswith(("https://", "http://localhost", "http://127.0.0.1")):
            raise EmailDeliveryError("KAIROS_PUBLIC_APP_URL must use HTTPS outside local development")
        return cls(host, port, username, password, sender, app_name, security, public_app_url)


def delivery_configured() -> bool:
    return EmailSettings.from_env() is not None


def invite_url(token: str) -> str | None:
    public_app_url = (os.getenv("KAIROS_PUBLIC_APP_URL") or "").strip().rstrip("/")
    if not public_app_url:
        return None
    return f"{public_app_url}/?view=admin&invite={quote(token, safe='')}"


def _send(message: EmailMessage, settings: EmailSettings | None = None) -> None:
    settings = settings or EmailSettings.from_env()
    if settings is None:
        raise EmailDeliveryError(
            "Email delivery is not configured. Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, "
            "and KAIROS_PUBLIC_APP_URL."
        )
    message["From"] = settings.sender if "<" in settings.sender else formataddr((settings.app_name, settings.sender))
    try:
        if settings.security == "ssl":
            with smtplib.SMTP_SSL(settings.host, settings.port, timeout=15, context=ssl.create_default_context()) as smtp:
                smtp.login(settings.username, settings.password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(settings.host, settings.port, timeout=15) as smtp:
                smtp.ehlo()
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
                smtp.login(settings.username, settings.password)
                smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailDeliveryError("SMTP could not deliver the message. Check the mail host, credentials, and sender configuration.") from exc


def _format_expiration(value: str) -> str:
    """Render an invitation expiry as readable UTC instead of a raw ISO value."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        parsed = parsed.astimezone(timezone.utc)
        hour = parsed.hour % 12 or 12
        meridiem = "AM" if parsed.hour < 12 else "PM"
        return f"{parsed.strftime('%B')} {parsed.day}, {parsed.year} at {hour}:{parsed.minute:02d} {meridiem} UTC"
    except (TypeError, ValueError):
        return value


def _branded_html(
    *, preheader: str, eyebrow: str, title: str, body_html: str,
    cta_label: str, cta_url: str, footer_note: str,
) -> str:
    """Build a Gmail-safe, inline-styled Kairos message using the app palette."""
    return f"""<!doctype html>
<html lang="en"><body style="margin:0;padding:0;background:#F3F4F6;color:#0B0B0C;font-family:Arial,'Segoe UI',sans-serif;-webkit-text-size-adjust:100%;">
<div style="display:none!important;visibility:hidden;opacity:0;color:transparent;height:0;width:0;overflow:hidden;mso-hide:all">{escape(preheader)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#F3F4F6" style="width:100%;background:#F3F4F6;border-collapse:collapse;">
  <tr><td align="center" style="padding:32px 14px;">
    <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" bgcolor="#FFFFFF" style="width:100%;max-width:600px;background:#FFFFFF;border:2px solid #0B0B0C;border-radius:18px;box-shadow:0 5px 0 #0B0B0C;border-collapse:separate;border-spacing:0;overflow:hidden;">
      <tr><td bgcolor="#E8F0FE" style="padding:22px 28px;background:#E8F0FE;border-bottom:2px solid #0B0B0C;">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
          <td align="center" valign="middle" width="42" height="42" bgcolor="#FBBC04" style="width:42px;height:42px;background:#FBBC04;border:2px solid #0B0B0C;border-radius:11px;box-shadow:3px 3px 0 #0B0B0C;color:#0B0B0C;font-size:22px;font-weight:800;">K</td>
          <td style="padding-left:13px;color:#0B0B0C;">
            <div style="font-size:18px;line-height:1.1;font-weight:800;letter-spacing:1.4px;">KAIROS</div>
            <div style="padding-top:4px;color:#5F6368;font-family:Consolas,Menlo,monospace;font-size:9px;letter-spacing:1.5px;">METADATA ENGINE</div>
          </td>
        </tr></table>
      </td></tr>
      <tr><td style="padding:32px 28px 30px;background:#FFFFFF;">
        <div style="margin:0 0 10px;color:#5F6368;font-family:Consolas,Menlo,monospace;font-size:10px;font-weight:700;letter-spacing:1.8px;text-transform:uppercase;">{escape(eyebrow)}</div>
        <h1 style="margin:0 0 16px;color:#0B0B0C;font-family:Arial,'Segoe UI',sans-serif;font-size:30px;line-height:1.16;font-weight:800;letter-spacing:-.7px;">{title}</h1>
        <div style="color:#3C4043;font-size:16px;line-height:1.65;">{body_html}</div>
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin-top:24px;border-collapse:separate;">
          <tr><td align="center" bgcolor="#FBBC04" style="background:#FBBC04;border:2px solid #0B0B0C;border-radius:999px;box-shadow:0 4px 0 #0B0B0C;">
            <a href="{escape(cta_url, quote=True)}" style="display:inline-block;padding:13px 23px;color:#0B0B0C;font-size:15px;line-height:1.2;font-weight:700;text-decoration:none;">{escape(cta_label)} &nbsp;→</a>
          </td></tr>
        </table>
        <p style="margin:23px 0 0;color:#5F6368;font-size:13px;line-height:1.6;">{footer_note}</p>
      </td></tr>
      <tr><td bgcolor="#F3F4F6" style="padding:16px 28px;background:#F3F4F6;border-top:1px solid #DADCE0;color:#5F6368;font-family:Consolas,Menlo,monospace;font-size:10px;line-height:1.6;letter-spacing:.5px;">
        KAIROS &nbsp;·&nbsp; EVIDENCE-FIRST LINEAGE<br><span style="font-family:Arial,'Segoe UI',sans-serif;font-size:11px;letter-spacing:0;">You received this message because of activity on your Kairos account.</span>
      </td></tr>
    </table>
  </td></tr>
</table></body></html>"""


def send_workspace_invitation(to_email: str, token: str, expires_at: str) -> str:
    settings = EmailSettings.from_env()
    if settings is None:
        raise EmailDeliveryError(
            "Email delivery is not configured. Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, "
            "and KAIROS_PUBLIC_APP_URL."
        )
    url = f"{settings.public_app_url}/?view=admin&invite={quote(token, safe='')}"
    readable_expiry = _format_expiration(expires_at)
    message = EmailMessage()
    message["To"] = to_email
    message["Subject"] = "You are invited to Kairos"
    message.set_content(
        "You are invited to join a Kairos workspace.\n\n"
        f"Accept your invitation: {url}\n\n"
        f"This link expires {readable_expiry}. It only works for the email address this invitation was sent to."
    )
    message.add_alternative(
        _branded_html(
            preheader="You have a new Kairos workspace invitation.",
            eyebrow="Workspace invitation",
            title="You’re invited to Kairos.",
            body_html=(
                "You’ve been invited to join a Kairos workspace and explore its metadata catalog."
                f"<div style=\"margin-top:18px;padding:13px 15px;border:1px solid #C7D7F5;border-radius:12px;background:#E8F0FE;color:#263238;font-size:13px;\">"
                f"<strong style=\"color:#0B0B0C;\">Link expires:</strong> {escape(readable_expiry)}"
                "</div>"
            ),
            cta_label="Accept invitation",
            cta_url=url,
            footer_note="For your security, sign in with the email address this invitation was sent to. The link expires after seven days.",
        ),
        subtype="html",
    )
    _send(message, settings)
    return url


def send_welcome_email(to_email: str, display_name: str | None = None) -> None:
    settings = EmailSettings.from_env()
    if settings is None:
        raise EmailDeliveryError(
            "Email delivery is not configured. Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, "
            "and KAIROS_PUBLIC_APP_URL."
        )
    name = (display_name or "there").strip() or "there"
    safe_name = escape(name)
    url = settings.public_app_url
    message = EmailMessage()
    message["To"] = to_email
    message["Subject"] = "Welcome to Kairos"
    message.set_content(
        f"Hello {name},\n\nWelcome to Kairos. Your account is ready.\n"
        f"Open your workspace: {url}\n\nKairos · Evidence-first lineage"
    )
    message.add_alternative(
        _branded_html(
            preheader="Your Kairos workspace is ready.",
            eyebrow="Welcome to your workspace",
            title=f"Hello {safe_name}.",
            body_html=(
                "Welcome to Kairos. Your account is ready. Your metadata workspace is where catalog context, "
                "ownership, and lineage come together."
            ),
            cta_label="Open my workspace",
            cta_url=url,
            footer_note="You can return to your workspace at any time using the button above.",
        ),
        subtype="html",
    )
    _send(message, settings)
