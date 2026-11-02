"""Fail-closed guarantees of the database workspace scope.

The API connects with a login that is privileged on the shared Supabase project
(``postgres`` holds ``BYPASSRLS``), so row-level security only protects tenants
while the connection is running as the restricted ``kairos_app`` role.  Every
check here asserts that a *missing or ineffective* role switch raises instead of
silently leaving a privileged connection usable, and that no query runs before
the scope is known to be applied.

These are offline tests: the connection is a fake that records statements and
reports whatever role the test asks for.
"""
from __future__ import annotations

import pytest

from backend.app import db


class _FakeCursor:
    """Records executed SQL and answers ``SELECT current_user`` with ``role``."""

    def __init__(self, role: str) -> None:
        self.role = role
        self.statements: list[tuple[str, tuple | None]] = []
        self._row = None

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, sql, params=None):
        self.statements.append((" ".join(sql.split()), params))
        self._row = (self.role,) if "current_user" in sql else None

    def fetchone(self):
        return self._row


class _FakeConn:
    def __init__(self, role: str) -> None:
        self.cursor_obj = _FakeCursor(role)
        self.rolled_back = False

    def cursor(self, *args, **kwargs):
        return self.cursor_obj

    def rollback(self) -> None:
        self.rolled_back = True

    @property
    def statements(self) -> list[tuple[str, tuple | None]]:
        return self.cursor_obj.statements

    def executed(self, needle: str) -> bool:
        return any(needle in sql for sql, _ in self.statements)


@pytest.fixture
def scoped_workspace():
    """Set the request-scoped workspace, then always reset it."""
    token = db.set_workspace_id("11111111-1111-4111-8111-111111111111")
    try:
        yield "11111111-1111-4111-8111-111111111111"
    finally:
        db.reset_workspace_id(token)


def test_missing_workspace_context_raises_before_touching_the_database():
    """Without an authenticated workspace, no statement may be issued at all."""
    token = db.set_workspace_id(None)
    try:
        conn = _FakeConn("postgres")
        with pytest.raises(RuntimeError, match="workspace context is missing"):
            db._apply_workspace_scope(conn)
        assert conn.statements == []
    finally:
        db.reset_workspace_id(token)


def test_privileged_role_still_active_raises_and_never_sets_workspace(scoped_workspace):
    """If ``SET LOCAL ROLE`` did not take effect, the request must be refused.

    This is the fail-open case that matters: the login can bypass RLS, so a
    silent no-op role switch would expose every workspace.
    """
    conn = _FakeConn("postgres")
    with pytest.raises(RuntimeError, match="expected 'kairos_app'"):
        db._apply_workspace_scope(conn)
    assert conn.executed("SET LOCAL ROLE kairos_app")
    # The workspace must not be advertised to a connection that is still privileged.
    assert not conn.executed("set_config")


def test_effective_role_switch_applies_workspace_in_the_same_transaction(scoped_workspace):
    conn = _FakeConn("kairos_app")
    db._apply_workspace_scope(conn)
    role_index = next(
        i for i, (sql, _) in enumerate(conn.statements) if "SET LOCAL ROLE" in sql
    )
    config_index = next(
        i for i, (sql, _) in enumerate(conn.statements) if "set_config" in sql
    )
    # SET LOCAL ROLE is transaction-scoped, so the workspace setting must follow
    # it inside this transaction rather than in a later one.
    assert role_index < config_index
    sql, params = conn.statements[config_index]
    assert "true" in sql, "set_config must be transaction-local (is_local = true)"
    assert params == (scoped_workspace,)


def test_get_conn_returns_the_connection_when_scope_fails(monkeypatch):
    """A refused scope must not leak a privileged connection back into use."""
    conn = _FakeConn("postgres")
    returned: list[object] = []

    class _Pool:
        def getconn(self):
            return conn

        def putconn(self, connection, close=False):
            returned.append(connection)

    monkeypatch.setattr(db, "_get_pool", lambda: _Pool())
    token = db.set_workspace_id("22222222-2222-4222-8222-222222222222")
    try:
        with pytest.raises(RuntimeError, match="expected 'kairos_app'"):
            with db.get_conn():
                pytest.fail("the body must not run without a verified scope")
    finally:
        db.reset_workspace_id(token)

    assert returned == [conn]
    assert conn.rolled_back
