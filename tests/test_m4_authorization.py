"""Authorization tests for the M4 routers, exercised through FastAPI.

These tests deliberately do **not** replace ``require_role``. They override only
``require_user`` (the verified-Supabase boundary, which cannot run offline) and
supply the workspace/role state that ``require_user`` would normally establish
via ``set_workspace_id``. Everything after that — the role lookup, the rank
comparison, the 401/403 responses, the fail-closed paths — is the production
code path.

No database is contacted: ``get_conn`` is replaced by a small double that models
the membership table lookups the guard performs.
"""
from __future__ import annotations

from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from backend.app import db as db_module
from backend.app.api.routes import governance, governance_registry, membership, quality
from backend.app.auth import require_user
from backend.app.main import app

WORKSPACE_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
WORKSPACE_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

VIEWER = "11111111-1111-4111-8111-111111111111"
EDITOR = "22222222-2222-4222-8222-222222222222"
ADMIN = "33333333-3333-4333-8333-333333333333"
OWNER = "44444444-4444-4444-8444-444444444444"
STRANGER = "55555555-5555-4555-8555-555555555555"

TERM_ID = "66666666-6666-4666-8666-666666666666"


class _MembershipStore:
    """The workspace_member rows the guard is allowed to see."""

    def __init__(self, roles=None, has_table=True):
        self.roles = dict(roles or {})
        self.has_table = has_table


class _MembershipCursor:
    """Default psycopg2 row shape (tuples), which is what the guard uses."""

    def __init__(self, store: _MembershipStore):
        self._store = store
        self._one = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=()):
        sql = " ".join(query.split())
        if sql.startswith("SELECT to_regclass"):
            self._one = ("public.workspace_member",) if self._store.has_table else (None,)
        elif sql.startswith("SELECT role FROM workspace_member"):
            workspace_id, user_id = params
            role = self._store.roles.get((workspace_id, user_id))
            self._one = (role,) if role else None
        else:  # pragma: no cover - unexpected query is a test bug
            raise AssertionError(f"Unexpected membership SQL: {sql}")

    def fetchone(self):
        return self._one


class _MembershipConnection:
    def __init__(self, store):
        self._store = store

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def cursor(self, *_args, **_kwargs):
        return _MembershipCursor(self._store)


class _Row(dict):
    """RealDictRow-compatible row used by the governance route doubles."""

    __getattr__ = dict.__getitem__


class _RouteCursor:
    """Serves only the statements of the two glossary writes under test."""

    def __init__(self):
        self.rowcount = 0
        self._one = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=()):
        sql = " ".join(query.split())
        if "to_regclass" in sql:
            self._one = _Row(relation="public.glossary_term")
        elif sql.startswith("INSERT INTO glossary_term"):
            self._one = _Row(
                id=TERM_ID,
                name=params[0],
                definition=params[1],
                status="DRAFT",
                created_at="2026-01-01T00:00:00Z",
            )
        elif sql.startswith("UPDATE glossary_term SET status='APPROVED'"):
            self._one = _Row(id=str(params[1]), status="APPROVED", updated_at="2026-01-01T00:00:00Z")
        else:  # pragma: no cover - unexpected query is a test bug
            raise AssertionError(f"Unexpected route SQL: {sql}")

    def fetchone(self):
        return self._one

    def fetchall(self):
        return []


class _RouteConnection:
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def cursor(self, *_args, **_kwargs):
        return _RouteCursor()


class _WorkspaceContext:
    """Stands in for the ContextVar ``require_user`` populates."""

    def __init__(self, workspace_id):
        self._workspace_id = workspace_id

    def get(self):
        return self._workspace_id


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _authenticate(monkeypatch, user_id, *, role=None, workspace=WORKSPACE_A, has_table=True):
    """Wire the verified-user boundary and the workspace/role state.

    ``require_user`` is the only dependency replaced; ``require_role`` executes
    for real against the membership double.
    """
    app.dependency_overrides[require_user] = lambda: {"id": user_id}

    roles = {(workspace, user_id): role} if role else {}
    store = _MembershipStore(roles=roles, has_table=has_table)

    @contextmanager
    def membership_conn():
        yield _MembershipConnection(store)

    monkeypatch.setattr(membership, "get_conn", membership_conn)
    monkeypatch.setattr(db_module, "_workspace_id", _WorkspaceContext(workspace))

    @contextmanager
    def route_conn():
        yield _RouteConnection()

    monkeypatch.setattr(governance_registry, "get_conn", route_conn)
    monkeypatch.setattr(governance, "get_conn", route_conn)
    monkeypatch.setattr(quality, "get_conn", route_conn)
    return store


def _term_payload():
    return {"name": "Customer", "definition": "A person who purchased."}


# -- authentication --------------------------------------------------------------


def test_unauthenticated_request_is_rejected_before_any_workspace_lookup(client, monkeypatch):
    called = False

    @contextmanager
    def membership_conn():  # pragma: no cover - must never run
        nonlocal called
        called = True
        yield _MembershipConnection(_MembershipStore())

    monkeypatch.setattr(membership, "get_conn", membership_conn)

    response = client.get("/api/v1/governance/terms")

    assert response.status_code == 401
    assert called is False


def test_unauthenticated_write_is_rejected(client):
    response = client.post("/api/v1/governance/terms", json=_term_payload())
    assert response.status_code == 401


# -- editor-level writes ---------------------------------------------------------


def test_viewer_cannot_create_a_glossary_term(client, monkeypatch):
    _authenticate(monkeypatch, VIEWER, role="viewer")

    response = client.post("/api/v1/governance/terms", json=_term_payload())

    assert response.status_code == 403
    assert "editor" in response.json()["detail"]


def test_viewer_cannot_create_a_quality_assertion(client, monkeypatch):
    _authenticate(monkeypatch, VIEWER, role="viewer")

    response = client.post(
        "/api/v1/quality/assertions",
        json={
            "dataset_id": "77777777-7777-4777-8777-777777777777",
            "name": "row count",
            "assertion_type": "completeness",
        },
    )

    assert response.status_code == 403


def test_editor_can_create_a_glossary_term(client, monkeypatch):
    _authenticate(monkeypatch, EDITOR, role="editor")

    response = client.post("/api/v1/governance/terms", json=_term_payload())

    assert response.status_code == 201
    assert response.json()["id"] == TERM_ID


# -- owner/admin-only writes -----------------------------------------------------


def test_editor_cannot_approve_a_glossary_term(client, monkeypatch):
    _authenticate(monkeypatch, EDITOR, role="editor")

    response = client.post(f"/api/v1/governance/terms/{TERM_ID}/approve")

    assert response.status_code == 403
    assert "owner" in response.json()["detail"] or "admin" in response.json()["detail"]


@pytest.mark.parametrize("user_id,role", [(ADMIN, "admin"), (OWNER, "owner")])
def test_owner_or_admin_can_approve_a_glossary_term(client, monkeypatch, user_id, role):
    _authenticate(monkeypatch, user_id, role=role)

    response = client.post(f"/api/v1/governance/terms/{TERM_ID}/approve")

    assert response.status_code == 200
    assert response.json()["status"] == "APPROVED"


# -- fail-closed behaviour -------------------------------------------------------


def test_missing_workspace_context_fails_closed(client, monkeypatch):
    _authenticate(monkeypatch, EDITOR, role="editor", workspace=None)

    response = client.post("/api/v1/governance/terms", json=_term_payload())

    assert response.status_code == 403
    assert "workspace" in response.json()["detail"].lower()


def test_membership_table_missing_fails_closed_rather_than_allowing(client, monkeypatch):
    app.dependency_overrides[require_user] = lambda: {"id": EDITOR}
    store = _MembershipStore(has_table=False)

    @contextmanager
    def membership_conn():
        yield _MembershipConnection(store)

    monkeypatch.setattr(membership, "get_conn", membership_conn)
    monkeypatch.setattr(db_module, "_workspace_id", _WorkspaceContext(WORKSPACE_A))

    response = client.post("/api/v1/governance/terms", json=_term_payload())

    assert response.status_code == 503


def test_member_of_another_workspace_cannot_write(client, monkeypatch):
    """The role lookup is scoped by the authenticated workspace, not the user alone."""
    _authenticate(monkeypatch, STRANGER, role="owner", workspace=WORKSPACE_A)

    # The same user holds a role inside workspace B only.
    store = _MembershipStore(roles={(WORKSPACE_B, STRANGER): "owner"})
    monkeypatch.setattr(
        membership,
        "get_conn",
        lambda: _conn_context(_MembershipConnection(store)),
    )

    response = client.post("/api/v1/governance/terms", json=_term_payload())

    assert response.status_code == 403


def test_no_role_row_is_refused_even_when_the_user_is_authenticated(client, monkeypatch):
    _authenticate(monkeypatch, EDITOR, role=None)

    response = client.post("/api/v1/governance/terms", json=_term_payload())

    assert response.status_code == 403


# -- notifications have no role gate ---------------------------------------------


def test_notification_reads_are_available_to_every_active_member(client, monkeypatch):
    """Reading one's own inbox is authenticated-only, not role-gated."""
    _authenticate(monkeypatch, VIEWER, role="viewer")
    monkeypatch.setattr(
        "backend.app.api.routes.notifications.get_conn",
        _notifications_conn,
    )

    response = client.post("/api/v1/notifications/read-all")

    assert response.status_code == 200
    assert response.json() == {"updated": 0}


@contextmanager
def _conn_context(connection):
    yield connection


class _NotificationCursor:
    def __init__(self):
        self.rowcount = 0
        self._one = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=()):
        sql = " ".join(query.split())
        if sql.startswith("SELECT to_regclass"):
            self._one = _Row(relation="public.notification")
        elif sql.startswith("UPDATE notification SET read_at=now()"):
            self.rowcount = 0
        else:  # pragma: no cover
            raise AssertionError(f"Unexpected notification SQL: {sql}")

    def fetchone(self):
        return self._one


class _NotificationConnection:
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def cursor(self, *_args, **_kwargs):
        return _NotificationCursor()


@contextmanager
def _notifications_conn():
    yield _NotificationConnection()
