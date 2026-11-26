"""Offline tests for notification-to-email delivery."""
from __future__ import annotations

from backend.app.services import notification_delivery as delivery


class _Settings:
    @classmethod
    def from_env(cls):
        return object()


class _UnconfiguredSettings:
    @classmethod
    def from_env(cls):
        return None


class _Cursor:
    def __init__(self, preference):
        self.preference = preference
        self.one = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=()):
        sql = " ".join(query.split())
        if "to_regclass" in sql:
            self.one = {"relation": "public.notification_preference"}
        elif "FROM notification_preference" in sql:
            self.one = None if self.preference is None else {"email": self.preference}
        else:  # pragma: no cover - unexpected SQL is a test bug
            raise AssertionError(f"Unexpected SQL: {sql}")

    def fetchone(self):
        return self.one


class _Connection:
    def __init__(self, preference):
        self.preference = preference

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def cursor(self):
        return _Cursor(self.preference)


def _message():
    return delivery.NotificationMessage(
        recipient_user_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        event_type="FRESHNESS_BREACH",
        title="orders is STALE",
        detail={"dataset_id": "dataset-1"},
        action_path="/governance/freshness?asset=dataset-1",
    )


def _wire(monkeypatch, *, preference=None, email="owner@example.com"):
    sent = []
    monkeypatch.setattr(delivery, "EmailSettings", _Settings)
    monkeypatch.setattr(delivery, "get_conn", lambda: _Connection(preference))
    monkeypatch.setattr(delivery, "resolve_user_email", lambda _user_id: email)
    monkeypatch.setattr(
        delivery,
        "send_notification_email",
        lambda *args, **kwargs: sent.append((args, kwargs)),
    )
    return sent


def test_notification_email_is_sent_when_no_preference_exists(monkeypatch):
    sent = _wire(monkeypatch)

    delivery.dispatch_notification_emails([_message()])

    assert len(sent) == 1
    args, kwargs = sent[0]
    assert args == ("owner@example.com",)
    assert kwargs == {
        "event_type": "FRESHNESS_BREACH",
        "title": "orders is STALE",
        "action_path": "/?view=freshness&asset=dataset-1",
    }


def test_legacy_notification_action_paths_are_mapped_to_the_spa():
    assert delivery.app_action_path("/governance/freshness?asset=dataset-1") == "/?view=freshness&asset=dataset-1"
    assert delivery.app_action_path("/governance/incidents?id=incident-1") == "/?view=incidents&id=incident-1"
    assert delivery.app_action_path("/governance/incidents/incident-1") == "/?view=incidents&id=incident-1"
    assert delivery.app_action_path("/?view=freshness&asset=dataset-1") == "/?view=freshness&asset=dataset-1"


def test_explicit_email_opt_out_skips_delivery(monkeypatch):
    sent = _wire(monkeypatch, preference=False)

    delivery.dispatch_notification_emails([_message()])

    assert sent == []


def test_missing_recipient_email_does_not_raise(monkeypatch):
    sent = _wire(monkeypatch, email=None)

    delivery.dispatch_notification_emails([_message()])

    assert sent == []


def test_unconfigured_smtp_skips_without_looking_up_recipient(monkeypatch):
    monkeypatch.setattr(delivery, "EmailSettings", _UnconfiguredSettings)
    monkeypatch.setattr(
        delivery,
        "resolve_user_email",
        lambda _user_id: (_ for _ in ()).throw(AssertionError("should not run")),
    )

    delivery.dispatch_notification_emails([_message()])


def test_delivery_failure_never_raises_into_the_request(monkeypatch):
    _wire(monkeypatch)

    def fail(*_args, **_kwargs):
        raise RuntimeError("smtp unavailable")

    monkeypatch.setattr(delivery, "send_notification_email", fail)

    delivery.dispatch_notification_emails([_message()])
