"""M3 live storage checks against the configured shared Supabase project.

Opt in with ``KAIROS_LIVE_INGEST_TESTS=1`` plus ``DATABASE_URL`` in ``.env``.
Without that, the whole module is skipped so the offline suite never depends on
network or shared-database state.

Everything runs inside one transaction that is rolled back, so the shared
catalog is never modified.  This exercises the real schema, the restricted
``kairos_app`` role, and workspace RLS: import once, replay idempotently, then
prove a second workspace can neither collide with nor read the first.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import pytest
from dotenv import load_dotenv
from fastapi import HTTPException
from psycopg2.extras import RealDictCursor

from backend.app.api.routes.ingestion import _canonical, _persist_import
from backend.app.schemas.ingestion import ImportEnvelope

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)


def _opted_in() -> bool:
    requested = os.getenv("KAIROS_LIVE_INGEST_TESTS", "").strip().lower() in {"1", "true", "yes"}
    return requested and bool(os.getenv("DATABASE_URL"))


pytestmark = pytest.mark.skipif(
    not _opted_in(),
    reason=(
        "Live ingestion storage tests are opt-in. Set KAIROS_LIVE_INGEST_TESTS=1 "
        "together with DATABASE_URL to run them against the shared Supabase project."
    ),
)


def _envelope(**overrides) -> ImportEnvelope:
    data = {
        "contract_version": "kairos.ingest.v1",
        "source": {"kind": "upload", "ref": "live-graph.json"},
        "idempotency_key": "live-test-001",
        "assets": [
            {"id": "raw", "name": "live_raw_orders", "namespace": "live/demo/raw", "type": "table"},
            {"id": "model", "name": "live_orders", "namespace": "live/demo/model", "type": "model"},
        ],
        "relationships": [{"source_id": "raw", "target_id": "model", "type": "declared_dependency"}],
    }
    data.update(overrides)
    return ImportEnvelope.model_validate(data)


def _scope(cur, workspace_id: str) -> None:
    cur.execute("SET LOCAL ROLE kairos_app")
    cur.execute("SELECT set_config('kairos.workspace_id', %s, true)", (workspace_id,))


@pytest.fixture
def db():
    conn = psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=15)
    try:
        yield conn
    finally:
        # Never persist test catalog rows to the shared project.
        conn.rollback()
        conn.close()


def test_commit_is_idempotent_and_workspace_isolated(db):
    cur = db.cursor(cursor_factory=RealDictCursor)
    workspace_a = str(uuid.uuid4())
    workspace_b = str(uuid.uuid4())
    cur.execute("SELECT kairos_ensure_personal_workspace(%s) AS id", (workspace_a,))
    ws_a = str(cur.fetchone()["id"])
    cur.execute("SELECT kairos_ensure_personal_workspace(%s) AS id", (workspace_b,))
    ws_b = str(cur.fetchone()["id"])
    assert ws_a != ws_b

    payload = _envelope()
    content, digest = _canonical(payload)
    now = datetime.now(timezone.utc)

    # ── Workspace A: one explicit commit ─────────────────────────────────────
    _scope(cur, ws_a)
    first = _persist_import(cur, ws_a, workspace_a, payload, content, digest, [], now)
    assert first["replayed"] is False
    assert first["counts"] == {"assets": 2, "relationships": 1}

    cur.execute("SELECT count(*)::int AS n FROM dataset WHERE source_system = 'upload'")
    assert cur.fetchone()["n"] == 2
    cur.execute("SELECT count(*)::int AS n FROM evidence WHERE source_system = 'upload'")
    assert cur.fetchone()["n"] == 1

    # ── Replaying the same workspace + key creates no duplicate ──────────────
    replay = _persist_import(cur, ws_a, workspace_a, payload, content, digest, [], now)
    assert replay["replayed"] is True
    assert replay["import_id"] == first["import_id"]
    cur.execute("SELECT count(*)::int AS n FROM import_run")
    assert cur.fetchone()["n"] == 1
    cur.execute("SELECT count(*)::int AS n FROM dataset WHERE source_system = 'upload'")
    assert cur.fetchone()["n"] == 2

    # ── Reusing a key for different content is rejected ──────────────────────
    changed = _envelope(assets=[{"id": "solo", "name": "live_solo", "namespace": "live/other", "type": "table"}],
                        relationships=[])
    changed_content, changed_digest = _canonical(changed)
    with pytest.raises(HTTPException) as error:
        _persist_import(cur, ws_a, workspace_a, changed, changed_content, changed_digest, [], now)
    assert error.value.status_code == 409

    # ── Workspace B: byte-identical content must not collide or be replayed ──
    _scope(cur, ws_b)
    other = _persist_import(cur, ws_b, workspace_b, payload, content, digest, [], now)
    assert other["replayed"] is False
    assert other["import_id"] != first["import_id"]
    assert other["counts"] == {"assets": 2, "relationships": 1}

    # ── Isolation: B cannot read A's catalog rows ────────────────────────────
    cur.execute("SELECT count(*)::int AS n FROM dataset")
    assert cur.fetchone()["n"] == 2
    cur.execute("SELECT count(*)::int AS n FROM import_run WHERE id = %s", (first["import_id"],))
    assert cur.fetchone()["n"] == 0
    cur.execute("SELECT count(*)::int AS n FROM evidence")
    assert cur.fetchone()["n"] == 1

    # ── The replay lookup cannot resolve another tenant's key ────────────────
    # `_persist_import` filters the idempotency lookup by workspace explicitly
    # rather than relying only on the policy.  Under B's scope, A's key must
    # return exactly B's own run and never A's.
    cur.execute(
        "SELECT id::text AS id FROM import_run WHERE idempotency_key = %s",
        (payload.idempotency_key,),
    )
    visible = [row["id"] for row in cur.fetchall()]
    assert visible == [other["import_id"]], "workspace B must not see workspace A's import run"


def test_scope_requires_the_restricted_role_and_fails_closed(db):
    """The role switch is the only tenant control on a BYPASSRLS login."""
    cur = db.cursor(cursor_factory=RealDictCursor)
    _scope(cur, str(uuid.uuid4()))
    cur.execute(
        """
        SELECT current_user AS role,
               (SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user) AS bypass
        """
    )
    row = cur.fetchone()
    assert row["role"] == "kairos_app"
    assert row["bypass"] is False

    # An unset workspace must hide everything, never fall back to the full table.
    cur.execute("SELECT set_config('kairos.workspace_id', '', true)")
    cur.execute("SELECT count(*)::int AS n FROM dataset")
    assert cur.fetchone()["n"] == 0
    cur.execute("SELECT count(*)::int AS n FROM import_run")
    assert cur.fetchone()["n"] == 0
