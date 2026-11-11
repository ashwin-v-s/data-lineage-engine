"""Offline notification persistence and recipient-authorization tests.

The cursor double here mirrors psycopg2's real row shapes: ``RealDictCursor``
yields dictionaries, the default cursor yields tuples.  An endpoint that reads
``row["relation"]`` from a default cursor raises ``TypeError`` immediately —
which is exactly the defect these tests now guard against, so the double must
never be more permissive than the driver.
"""
from __future__ import annotations

from contextlib import contextmanager
from uuid import UUID

import pytest
from fastapi import HTTPException
from psycopg2.extras import RealDictCursor

from backend.app.api.routes import notifications

USER_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
USER_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
NOTICE_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
OTHER_NOTICE_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
FOREIGN_NOTICE_ID = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"


class _Store:
    """Minimal in-memory stand-in for the two M4 notification tables."""

    def __init__(self, tables=("notification", "notification_preference")):
        self.tables = set(tables) if not isinstance(tables, set) else tables
        self.notifications = []
        self.preferences = {}

    def add(self, notice_id, recipient, read=False):
        self.notifications.append({"id": notice_id, "recipient_user_id": recipient, "read": read})


def _dict_row(**values):
    """A dict row with the attribute access RealDictRow also provides."""

    class _Row(dict):
        __getattr__ = dict.__getitem__

    return _Row(values)


class _Cursor:
    """A cursor whose row shape depends on the requested factory alone."""

    def __init__(self, store: _Store, dict_rows: bool):
        self._store = store
        self._dict_rows = dict_rows
        self.rowcount = 0
        self._one = None
        self._many = []

    # -- psycopg2 cursor protocol -------------------------------------------
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def _shape(self, row):
        if row is None:
            return None
        if self._dict_rows:
            return _dict_row(**row)
        return tuple(row.values())

    def execute(self, query, params=()):
        sql = " ".join(query.split())
        if "to_regclass" in sql:
            table = "notification_preference" if "notification_preference" in sql else "notification"
            self._one = self._shape(
                {"relation": f"public.{table}" if table in self._store.tables else None}
            )
        elif sql.startswith("UPDATE notification SET read_at=coalesce"):
            recipient, notification_ids = params
            # Model both the endpoint's recipient predicate and the RLS policy.
            self.rowcount = 0
            for notice in self._store.notifications:
                if (
                    notice["recipient_user_id"] == recipient
                    and notice["id"] in notification_ids
                ):
                    notice["read"] = True
                    self.rowcount += 1
            self._one = None
        elif sql.startswith("UPDATE notification SET read_at=now()"):
            (recipient,) = params
            self.rowcount = 0
            for notice in self._store.notifications:
                if notice["recipient_user_id"] == recipient and not notice["read"]:
                    notice["read"] = True
                    self.rowcount += 1
            self._one = None
        elif sql.startswith("INSERT INTO notification_preference"):
            user_id, event_type, in_app, email = params
            self._store.preferences[(user_id, event_type)] = {
                "event_type": event_type,
                "in_app": in_app,
                "email": email,
            }
            self._one = self._shape(self._store.preferences[(user_id, event_type)])
        elif sql.startswith("SELECT event_type,in_app,email FROM notification_preference"):
            (user_id,) = params
            self._many = [
                self._shape(row)
                for (owner, _event), row in self._store.preferences.items()
                if owner == user_id
            ]
        else:  # pragma: no cover - an unexpected query is a test bug
            raise AssertionError(f"Unexpected SQL: {sql}")

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._many


class _Conn:
    def __init__(self, store: _Store):
        self._store = store

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def cursor(self, *args, **kwargs):
        # psycopg2 ignores *args and honours cursor_factory from kwargs.
        return _Cursor(self._store, dict_rows=kwargs.get("cursor_factory") is RealDictCursor)


@contextmanager
def _connection_for(store: _Store):
    yield _Conn(store)


@pytest.fixture
def store(monkeypatch):
    """A store with both tables present, wired into the route module."""
    state = _Store()
    monkeypatch.setattr(notifications, "get_conn", lambda: _connection_for(state))
    return state


def _missing_table(monkeypatch):
    state = _Store(tables=set())
    monkeypatch.setattr(notifications, "get_conn", lambda: _connection_for(state))
    return state


# -- mark one read ---------------------------------------------------------------


def test_mark_read_marks_the_recipients_notification(store):
    from backend.app.api.routes.notifications import MarkReadInput, mark_read

    store.add(NOTICE_ID, USER_A)

    assert mark_read(MarkReadInput(notification_ids=[UUID(NOTICE_ID)]), {"id": USER_A}) == {"updated": 1}
    assert store.notifications[0]["read"] is True


def test_mark_read_is_limited_to_the_authenticated_recipient(store):
    from backend.app.api.routes.notifications import MarkReadInput, mark_read

    store.add(NOTICE_ID, USER_A)

    assert mark_read(MarkReadInput(notification_ids=[UUID(NOTICE_ID)]), {"id": USER_B}) == {"updated": 0}
    assert store.notifications[0]["read"] is False


def test_mark_read_ignores_notifications_the_caller_did_not_provide(store):
    from backend.app.api.routes.notifications import MarkReadInput, mark_read

    store.add(NOTICE_ID, USER_A)
    store.add(OTHER_NOTICE_ID, USER_A)

    result = mark_read(MarkReadInput(notification_ids=[UUID(NOTICE_ID)]), {"id": USER_A})

    assert result == {"updated": 1}
    assert store.notifications[1]["read"] is False


def test_mark_read_rejects_empty_or_oversized_batches(store):
    from backend.app.api.routes.notifications import MarkReadInput, mark_read

    with pytest.raises(HTTPException) as empty:
        mark_read(MarkReadInput(notification_ids=[]), {"id": USER_A})
    assert empty.value.status_code == 422

    with pytest.raises(HTTPException) as oversized:
        mark_read(
            MarkReadInput(notification_ids=[UUID(int=i + 1) for i in range(101)]),
            {"id": USER_A},
        )
    assert oversized.value.status_code == 422


def test_mark_read_returns_503_when_notification_storage_is_missing(monkeypatch):
    """A dict read on a tuple cursor used to raise TypeError (HTTP 500) here."""
    from backend.app.api.routes.notifications import MarkReadInput, mark_read

    _missing_table(monkeypatch)

    with pytest.raises(HTTPException) as error:
        mark_read(MarkReadInput(notification_ids=[UUID(NOTICE_ID)]), {"id": USER_A})
    assert error.value.status_code == 503
    assert "migration 0011" in error.value.detail


# -- mark all read ---------------------------------------------------------------


def test_mark_all_read_marks_only_the_recipients_unread_notifications(store):
    from backend.app.api.routes.notifications import mark_all_read

    store.add(NOTICE_ID, USER_A)
    store.add(OTHER_NOTICE_ID, USER_A, read=True)
    store.add(FOREIGN_NOTICE_ID, USER_B)

    assert mark_all_read({"id": USER_A}) == {"updated": 1}
    assert [notice["read"] for notice in store.notifications] == [True, True, False]


def test_mark_all_read_returns_503_when_notification_storage_is_missing(monkeypatch):
    from backend.app.api.routes.notifications import mark_all_read

    _missing_table(monkeypatch)

    with pytest.raises(HTTPException) as error:
        mark_all_read({"id": USER_A})
    assert error.value.status_code == 503


# -- preferences -----------------------------------------------------------------


def test_notification_event_type_is_validated(store):
    from backend.app.api.routes.notifications import PreferenceInput, set_preference

    with pytest.raises(HTTPException) as error:
        set_preference(PreferenceInput(event_type="ARBITRARY"), {"id": USER_A})
    assert error.value.status_code == 422


def test_notification_preference_round_trips_through_the_workspace_store(store):
    from backend.app.api.routes.notifications import PreferenceInput, get_preferences, set_preference

    saved = set_preference(
        PreferenceInput(event_type="FRESHNESS_BREACH", in_app=True, email=False),
        {"id": USER_A},
    )
    loaded = get_preferences({"id": USER_A})

    assert saved["event_type"] == "FRESHNESS_BREACH"
    assert loaded["preferences"] == [saved]


def test_preferences_return_503_when_the_preference_table_is_missing(monkeypatch):
    from backend.app.api.routes.notifications import get_preferences

    _missing_table(monkeypatch)

    with pytest.raises(HTTPException) as error:
        get_preferences({"id": USER_A})
    assert error.value.status_code == 503
