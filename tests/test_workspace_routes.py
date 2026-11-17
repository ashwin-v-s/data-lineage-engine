"""Offline regression tests for the workspace endpoints.

`kairos_workspace` is default-deny for the API role (FORCE RLS, deny policy,
no grants), so these endpoints must read memberships through
`kairos_list_user_workspaces(<verified user id>)`. The tests pin the mapping,
the current-workspace selection, the membership-scoped lookup, and the fact
that foreign and nonexistent ids are indistinguishable.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.app import db
from backend.app.api.routes import workspaces as workspaces_module

USER = "1ec1ddc9-096a-4562-9cd6-b29664e92ec4"
OWN = "da900221-1587-494d-b074-29842cf9772a"
FOREIGN = "80234193-bff1-45d3-90fa-25603a3ceb16"
MISSING = "00000000-0000-4000-8000-0000000000ff"


class _Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed_sql = None
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params=None):
        self.executed_sql = sql
        self.params = params

    def fetchone(self):
        return self.rows[0] if self.rows else None


class _Connection:
    def __init__(self, cursor):
        self.cursor_instance = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self, *_args, **_kwargs):
        return self.cursor_instance


@pytest.fixture
def install(monkeypatch):
    """Patch the route's connection factory and pin the current workspace."""
    cursor = _Cursor(rows=[])
    monkeypatch.setattr(workspaces_module, "get_conn", lambda: _Connection(cursor))
    token = db.set_workspace_id(OWN)
    try:
        def configure(rows):
            cursor.rows = rows
            return cursor
        yield configure
    finally:
        db.reset_workspace_id(token)


def test_me_workspace_selects_the_current_membership(install):
    cursor = install([(OWN, "Personal workspace", "owner", True)])

    body = workspaces_module.get_my_workspace(user={"id": USER})

    assert body == {
        "ok": True,
        "workspace": {
            "id": OWN,
            "name": "Personal workspace",
            "owner_id": USER,
            "created_at": None,
        },
    }
    assert "kairos_list_user_workspaces" in cursor.executed_sql
    assert "is_current" in cursor.executed_sql
    assert "kairos_workspace" not in cursor.executed_sql.replace(
        "kairos_list_user_workspaces", ""
    )
    assert cursor.params == (USER,)


def test_own_workspace_lookup_returns_the_membership_payload(install):
    cursor = install([(OWN, "Personal workspace", "owner", True)])

    body = workspaces_module.get_workspace(OWN, user={"id": USER})

    assert body["ok"] is True
    assert body["workspace"] == {
        "id": OWN,
        "name": "Personal workspace",
        "owner_id": USER,
        "created_at": None,
    }
    assert cursor.params == (USER, OWN)


def test_foreign_workspace_id_is_not_visible(install):
    cursor = install([])

    with pytest.raises(HTTPException) as error:
        workspaces_module.get_workspace(FOREIGN, user={"id": USER})

    assert error.value.status_code == 404
    # the lookup is restricted to the caller's own memberships
    assert cursor.params == (USER, FOREIGN)
    assert "kairos_workspace " not in cursor.executed_sql


def test_foreign_and_nonexistent_workspace_ids_are_indistinguishable(install):
    install([])
    with pytest.raises(HTTPException) as foreign:
        workspaces_module.get_workspace(FOREIGN, user={"id": USER})

    install([])
    with pytest.raises(HTTPException) as missing:
        workspaces_module.get_workspace(MISSING, user={"id": USER})

    assert foreign.value.status_code == missing.value.status_code == 404
    assert foreign.value.detail == missing.value.detail


def test_me_workspace_without_active_membership_returns_404(install):
    install([])

    with pytest.raises(HTTPException) as error:
        workspaces_module.get_my_workspace(user={"id": USER})

    assert error.value.status_code == 404
    assert error.value.detail == workspaces_module._NOT_FOUND_DETAIL


def test_non_owner_membership_does_not_claim_ownership(install):
    install([(OWN, "Shared workspace", "viewer", True)])

    body = workspaces_module.get_my_workspace(user={"id": USER})

    assert body["workspace"]["owner_id"] is None
    assert body["workspace"]["name"] == "Shared workspace"


def test_malformed_workspace_id_returns_404_without_querying(install):
    cursor = install([])

    with pytest.raises(HTTPException) as error:
        workspaces_module.get_workspace("not-a-uuid", user={"id": USER})

    assert error.value.status_code == 404
    assert error.value.detail == workspaces_module._NOT_FOUND_DETAIL
    assert cursor.executed_sql is None
