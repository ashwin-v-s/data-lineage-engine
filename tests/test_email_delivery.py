from __future__ import annotations

from email.message import EmailMessage

import pytest

from backend.app.services import email_delivery as mail


class _SMTP:
    messages = []
    logins = []

    def __init__(self, *args, **kwargs): self.args, self.kwargs = args, kwargs
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def ehlo(self): pass
    def starttls(self, **kwargs): pass
    def login(self, username, password): self.logins.append((username, password))
    def send_message(self, message): self.messages.append(message)


@pytest.fixture(autouse=True)
def smtp_env(monkeypatch):
    # Never inherit live developer SMTP secrets into unit tests. Individual
    # tests opt into the standard variable names explicitly below.
    for key in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM", "SMTP_APP_NAME"):
        monkeypatch.delenv(key, raising=False)
    for key, value in {
        "KAIROS_EMAIL_HOST": "smtp.example.test",
        "KAIROS_EMAIL_PORT": "587",
        "KAIROS_EMAIL_SECURITY": "starttls",
        "KAIROS_EMAIL_USERNAME": "mailer@example.test",
        "KAIROS_EMAIL_PASSWORD": "test-only-password",
        "KAIROS_EMAIL_FROM": "Kairos <mailer@example.test>",
        "KAIROS_PUBLIC_APP_URL": "https://kairos.example.test",
    }.items():
        monkeypatch.setenv(key, value)
    _SMTP.messages.clear()
    _SMTP.logins.clear()
    monkeypatch.setattr(mail.smtplib, "SMTP", _SMTP)


def test_invitation_email_contains_acceptance_url_and_expiry(monkeypatch):
    url = mail.send_workspace_invitation("invitee@gmail.com", "secret-token", "2026-11-14T00:00:00Z")
    assert url == "https://kairos.example.test/?view=admin&invite=secret-token"
    message = _SMTP.messages[0]
    assert isinstance(message, EmailMessage)
    assert message["To"] == "invitee@gmail.com"
    assert "secret-token" in message.get_body(preferencelist=("plain",)).get_content()
    assert "November 14, 2026" in message.get_body(preferencelist=("plain",)).get_content()
    assert _SMTP.logins == [("mailer@example.test", "test-only-password")]
    html = message.get_body(preferencelist=("html",)).get_content()
    assert "KAIROS" in html
    assert "#FBBC04" in html
    assert "Accept invitation" in html
    assert "November 14, 2026" in html
    assert "2026-11-14T00:00:00Z" not in html


def test_welcome_email_greets_signed_in_user():
    mail.send_welcome_email("member@gmail.com", "Kairos Member")
    message = _SMTP.messages[0]
    assert message["To"] == "member@gmail.com"
    assert "Hello Kairos Member" in message.get_body(preferencelist=("plain",)).get_content()
    assert "https://kairos.example.test" in message.get_body(preferencelist=("plain",)).get_content()
    html = message.get_body(preferencelist=("html",)).get_content()
    assert "Hello Kairos Member." in html
    assert "EVIDENCE-FIRST LINEAGE" in html
    assert "Open my workspace" in html


def test_welcome_email_escapes_name_in_branded_html():
    mail.send_welcome_email("member@gmail.com", "<Kairos Member>")
    html = _SMTP.messages[0].get_body(preferencelist=("html",)).get_content()
    assert "&lt;Kairos Member&gt;" in html
    assert "<h1>Hello <Kairos Member>" not in html


def test_missing_smtp_configuration_fails_without_claiming_delivery(monkeypatch):
    monkeypatch.delenv("KAIROS_EMAIL_PASSWORD")
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    with pytest.raises(mail.EmailDeliveryError, match="not configured"):
        mail.send_welcome_email("member@gmail.com")
    assert _SMTP.messages == []


def test_standard_smtp_variables_and_app_name(monkeypatch):
    for key in ("KAIROS_EMAIL_HOST", "KAIROS_EMAIL_PORT", "KAIROS_EMAIL_USERNAME", "KAIROS_EMAIL_PASSWORD", "KAIROS_EMAIL_FROM"):
        monkeypatch.delenv(key, raising=False)
    for key, value in {
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "kairos.sender@gmail.com",
        "SMTP_PASSWORD": "test-app-password",
        "SMTP_FROM": "kairos.sender@gmail.com",
        "SMTP_APP_NAME": "Kairos Demo",
    }.items():
        monkeypatch.setenv(key, value)

    settings = mail.EmailSettings.from_env()
    assert settings is not None
    assert settings.host == "smtp.gmail.com"
    assert settings.port == 587
    assert settings.username == "kairos.sender@gmail.com"
    assert settings.password == "test-app-password"
    assert settings.sender == "kairos.sender@gmail.com"
    assert settings.app_name == "Kairos Demo"

    mail.send_welcome_email("member@gmail.com")
    assert _SMTP.messages[0]["From"] == "Kairos Demo <kairos.sender@gmail.com>"
