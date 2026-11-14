"""
Offline HTTP tests for POST /api/v1/ingest/preview and /api/v1/ingest/commit
covering demos 5 (sql_file) and 6 (dbt_manifest).

All tests run without a live database.  psycopg2 is stubbed at import time and
get_conn() is patched per-test.  require_user is overridden via
app.dependency_overrides.

Contracts verified
──────────────────
SQL file (demo 5)
  S1  preview returns ok=True with ≥3 assets and ≥2 relationships for
      demo_revenue.sql (CREATE TABLE ... AS SELECT ... JOIN).
  S2  preview returns commit_ready=True when the import_run table exists.
  S3  preview returns commit_ready=False + commit_blocker message when the
      import_run table is absent.
  S4  A comment-only SQL file is accepted but produces 0 relationships.
  S5  A plain SELECT with no declared target produces 0 relationships.
  S6  content as a dict (old JS JSON.parse bug) is handled without crashing.
  S7  Blank filename still succeeds (server uses the default).
  S8  Normalized payload preserves the original SQL text.
  S9  SQL relationships use edge_type='sql_static_candidate'.
  S10 Unauthenticated request returns 401.

dbt manifest (demo 6)
  D1  preview returns assets=3 and relationships=2 for the demo fixture.
  D2  Preview opens exactly one DB connection (migration check only).
  D3  Sending manifest content as an already-serialized JSON string works.
  D4  Empty manifest returns 422 with a resource diagnostic.
  D5  A list manifest returns 422.
  D6  dbt relationships use edge_type='declared_dependency'.
  D7  Model asset carries column metadata (order_id, amount).
  D8  Unauthenticated request returns 401.

Commit path
  C1  sql_file commit returns ok=True with persisted_assets and
      persisted_relationships counts.
  C2  dbt_manifest commit returns ok=True with correct counts.
  C3  Replaying the same idempotency_key returns replayed=True.
  C4  Reusing a key with different content returns 409.
  C5  Commit without import_run table returns 503.

Evidence classification
  E1  All static-file relationships carry evidence_class=DECLARED_METADATA.
  E2  No runtime evidence records appear in a static import.
"""
from __future__ import annotations

import json
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ── psycopg2 stub — must be injected BEFORE any backend import ───────────────
if "psycopg2" not in sys.modules:
    _stub = ModuleType("psycopg2")
    _stub.connect = MagicMock()
    _stub.OperationalError = Exception
    _stub.Error = Exception
    _extras = ModuleType("psycopg2.extras")
    _extras.RealDictCursor = dict
    _extras.Json = lambda v: v          # pass-through; not inspected in tests
    _pool = ModuleType("psycopg2.pool")
    _pool.ThreadedConnectionPool = MagicMock()
    sys.modules["psycopg2"] = _stub
    sys.modules["psycopg2.extras"] = _extras
    sys.modules["psycopg2.pool"] = _pool

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.auth import require_user  # noqa: E402
from backend.app.main import app           # noqa: E402

# ── Demo fixture content ─────────────────────────────────────────────────────
_FIXTURES = Path(__file__).resolve().parents[1] / "docs" / "demo-fixtures"
SQL_FIXTURE = (_FIXTURES / "demo_revenue.sql").read_text(encoding="utf-8")
DBT_FIXTURE = json.loads((_FIXTURES / "manifest.json").read_text(encoding="utf-8"))

# ── Fixed test user ───────────────────────────────────────────────────────────
_USER = {"id": str(uuid.uuid4()), "email": "demo@kairos.test"}

# ── DB cursor mock ────────────────────────────────────────────────────────────

class _Cursor:
    """Minimal cursor — returns successive rows from a pre-loaded list."""

    def __init__(self, rows=None):
        self._rows = list(rows or [])
        self._call = 0
        self.rowcount = 1

    def execute(self, sql="", params=None):
        self._call += 1

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


class _Conn:
    def __init__(self, cursor: _Cursor | None = None):
        self._cursor = cursor or _Cursor()

    def cursor(self, **_):
        return self._cursor

    def commit(self):
        pass

    def rollback(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


# ── Convenience factories ─────────────────────────────────────────────────────

@contextmanager
def _preview_conn():
    """Preview path: one DB round-trip to check import_run presence."""
    yield _Conn(_Cursor(rows=[{"import_run": "import_run"}]))


@contextmanager
def _no_migration_conn():
    """import_run table absent → commit_ready=False."""
    yield _Conn(_Cursor(rows=[{"import_run": None}]))


def _commit_rows(num_assets: int, num_relationships: int) -> list:
    """
    Build the fetchone() return sequence for a full commit.

    Exact call sequence in _commit_import (each line = one execute; ✓ = fetchone follows):
      ✓  to_regclass('public.import_run')   → {"import_run": "import_run"}
         pg_advisory_xact_lock              → no fetchone
      ✓  SELECT idempotency                 → None  (new run)
      ✓  INSERT import_run                  → {"id": run_id}
         INSERT raw_event                   → no fetchone
      × num_assets:
        ✓ INSERT dataset                   → {"id": dataset_id}
           (SQL/dbt adapters produce 0 columns, so no column_record inserts)
      × num_relationships:
        ✓ INSERT lineage_edge              → {"id": edge_id}  (non-conflict path)
        ✓ INSERT evidence                  → {"id": evidence_id}
           INSERT edge_temporal_version    → no fetchone
         UPDATE import_run                 → no fetchone
    """
    run_id = str(uuid.uuid4())
    rows: list = [
        {"import_run": "import_run"},   # to_regclass ✓
        # advisory lock — no fetchone, so NOT in rows
        None,                            # SELECT idempotency ✓ → None = new
        {"id": run_id},                  # INSERT import_run ✓
        # INSERT raw_event — no fetchone
    ]
    for _ in range(num_assets):
        rows.append({"id": str(uuid.uuid4())})   # INSERT dataset ✓

    for _ in range(num_relationships):
        rows.append({"id": str(uuid.uuid4())})   # INSERT lineage_edge ✓
        rows.append({"id": str(uuid.uuid4())})   # INSERT evidence ✓
        # INSERT edge_temporal_version — no fetchone
    # UPDATE import_run — no fetchone
    return rows


@contextmanager
def _commit_conn(num_assets: int = 4, num_relationships: int = 2):
    yield _Conn(_Cursor(rows=_commit_rows(num_assets, num_relationships)))


# ── Test client ───────────────────────────────────────────────────────────────
client = TestClient(app)


def _auth():
    """Set the user override; returns a cleanup callable."""
    app.dependency_overrides[require_user] = lambda: _USER

    def _clear():
        app.dependency_overrides.pop(require_user, None)

    return _clear


def _preview(kind: str, content: Any, filename: str = "test-file") -> Any:
    clear = _auth()
    try:
        return client.post(
            "/api/v1/ingest/preview",
            json={"kind": kind, "content": content, "filename": filename},
        )
    finally:
        clear()


def _commit(
    kind: str,
    content: Any,
    filename: str = "test-file",
    idempotency_key: str | None = None,
) -> Any:
    clear = _auth()
    try:
        return client.post(
            "/api/v1/ingest/commit",
            json={
                "kind": kind,
                "content": content,
                "filename": filename,
                "idempotency_key": idempotency_key or str(uuid.uuid4()),
            },
        )
    finally:
        clear()


# ═══════════════════════════════════════════════════════════════════════════════
# SQL FILE — demo 5
# ═══════════════════════════════════════════════════════════════════════════════

class TestSqlFilePreview:

    def test_s1_demo_fixture_returns_assets_and_relationships(self):
        """demo_revenue.sql → ≥3 assets (file + target table + 2 sources) and ≥2 edges."""
        with patch("backend.app.api.routes.ingest.get_conn", side_effect=_preview_conn):
            resp = _preview("sql_file", SQL_FIXTURE, "demo_revenue.sql")

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["ok"] is True
        p = body["preview"]
        assert p["assets"] >= 3,        f"expected ≥3 assets, got {p['assets']}"
        assert p["relationships"] >= 2, f"expected ≥2 relationships, got {p['relationships']}"

    def test_s1_provenance_is_sqlglot(self):
        with patch("backend.app.api.routes.ingest.get_conn", side_effect=_preview_conn):
            resp = _preview("sql_file", SQL_FIXTURE, "demo_revenue.sql")

        body = resp.json()
        assert body["preview"]["provenance"]["adapter"] == "kairos.sqlglot_file"

    def test_s2_commit_ready_true_when_migration_present(self):
        with patch("backend.app.api.routes.ingest.get_conn", side_effect=_preview_conn):
            resp = _preview("sql_file", SQL_FIXTURE, "demo_revenue.sql")

        body = resp.json()
        assert body["commit_ready"] is True
        assert body["commit_blocker"] is None

    def test_s3_commit_ready_false_when_migration_absent(self):
        with patch("backend.app.api.routes.ingest.get_conn", side_effect=_no_migration_conn):
            resp = _preview("sql_file", SQL_FIXTURE, "demo_revenue.sql")

        body = resp.json()
        assert body["commit_ready"] is False
        assert body["commit_blocker"] is not None
        assert "migration" in body["commit_blocker"].lower()

    def test_s4_comment_only_sql_produces_no_relationships(self):
        sql = "-- Static lineage example. This file is parsed; it is never executed.\n"
        with patch("backend.app.api.routes.ingest.get_conn", side_effect=_preview_conn):
            resp = _preview("sql_file", sql, "comment_only.sql")

        body = resp.json()
        assert body["ok"] is True
        assert body["preview"]["relationships"] == 0

    def test_s5_plain_select_produces_no_relationships(self):
        """Plain SELECT must not invent lineage — no declared target."""
        sql = "SELECT order_id, amount FROM raw.orders WHERE amount > 100;"
        with patch("backend.app.api.routes.ingest.get_conn", side_effect=_preview_conn):
            resp = _preview("sql_file", sql, "select_only.sql")

        body = resp.json()
        assert body["ok"] is True
        assert body["preview"]["relationships"] == 0, (
            "Plain SELECT must not produce lineage edges"
        )

    def test_s6_content_as_dict_returns_422(self):
        """
        Sending a dict as SQL content (the old JS JSON.parse bug) must return 422
        with a SQL_PARSE_ERROR diagnostic, not a 500 server crash.
        Fixed in ingestion/sql/static_file.py: non-string input is now rejected cleanly.
        """
        with patch("backend.app.api.routes.ingest.get_conn", side_effect=_preview_conn):
            resp = _preview("sql_file", {"sql": SQL_FIXTURE}, "bad.sql")

        assert resp.status_code == 422, (
            f"Dict content should be rejected with 422, got {resp.status_code}: {resp.text}"
        )
        detail = resp.json().get("detail", {})
        diagnostics = detail.get("diagnostics", [])
        assert any(d.get("code") == "SQL_PARSE_ERROR" for d in diagnostics), (
            f"Expected SQL_PARSE_ERROR diagnostic, got: {diagnostics}"
        )

    def test_s7_blank_filename_uses_default(self):
        with patch("backend.app.api.routes.ingest.get_conn", side_effect=_preview_conn):
            clear = _auth()
            try:
                resp = client.post(
                    "/api/v1/ingest/preview",
                    json={"kind": "sql_file", "content": SQL_FIXTURE},
                )
            finally:
                clear()

        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_s8_normalized_payload_preserves_original_sql(self):
        """The file asset in the normalized payload must carry the original SQL text."""
        with patch("backend.app.api.routes.ingest.get_conn", side_effect=_preview_conn):
            resp = _preview("sql_file", SQL_FIXTURE, "demo_revenue.sql")

        normalized = resp.json()["normalized"]
        file_assets = [a for a in normalized["assets"] if a.get("type") == "file"]
        assert file_assets, "Expected at least one file-type asset"
        assert "original_sql" in file_assets[0]["metadata"]
        assert "demo_order_revenue" in file_assets[0]["metadata"]["original_sql"]

    def test_s9_sql_relationships_use_sql_static_candidate_edge_type(self):
        with patch("backend.app.api.routes.ingest.get_conn", side_effect=_preview_conn):
            resp = _preview("sql_file", SQL_FIXTURE, "demo_revenue.sql")

        normalized = resp.json()["normalized"]
        for rel in normalized["relationships"]:
            assert rel["edge_type"] == "sql_static_candidate", (
                f"SQL relationships must use 'sql_static_candidate', got {rel['edge_type']!r}"
            )

    def test_s10_unauthenticated_returns_401(self):
        resp = client.post(
            "/api/v1/ingest/preview",
            json={"kind": "sql_file", "content": SQL_FIXTURE, "filename": "demo_revenue.sql"},
        )
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# dbt MANIFEST — demo 6
# ═══════════════════════════════════════════════════════════════════════════════

class TestDbtManifestPreview:

    def test_d1_demo_fixture_returns_3_assets_2_relationships(self):
        """manifest.json has 1 model + 2 sources = 3 assets, 2 declared dependencies."""
        with patch("backend.app.api.routes.ingest.get_conn", side_effect=_preview_conn):
            resp = _preview("dbt_manifest", DBT_FIXTURE, "manifest.json")

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["ok"] is True
        p = body["preview"]
        assert p["assets"] == 3,        f"expected 3 assets, got {p['assets']}"
        assert p["relationships"] == 2, f"expected 2 relationships, got {p['relationships']}"

    def test_d1_provenance_adapter_is_dbt_manifest(self):
        with patch("backend.app.api.routes.ingest.get_conn", side_effect=_preview_conn):
            resp = _preview("dbt_manifest", DBT_FIXTURE, "manifest.json")

        body = resp.json()
        assert body["preview"]["provenance"]["adapter"] == "kairos.dbt_manifest"

    def test_d2_preview_opens_exactly_one_db_connection(self):
        """Preview is read-only: one connection only (migration check)."""
        opened: list[int] = []

        @contextmanager
        def _tracking():
            opened.append(1)
            yield _Conn(_Cursor(rows=[{"import_run": "import_run"}]))

        with patch("backend.app.api.routes.ingest.get_conn", side_effect=_tracking):
            resp = _preview("dbt_manifest", DBT_FIXTURE, "manifest.json")

        assert resp.json()["ok"] is True
        assert len(opened) == 1, f"Preview must open exactly 1 connection, opened {len(opened)}"

    def test_d3_manifest_as_json_string_works(self):
        """Content may be a JSON string (server parses it)."""
        with patch("backend.app.api.routes.ingest.get_conn", side_effect=_preview_conn):
            resp = _preview("dbt_manifest", json.dumps(DBT_FIXTURE), "manifest.json")

        body = resp.json()
        assert body["ok"] is True
        assert body["preview"]["assets"] == 3

    def test_d4_empty_manifest_returns_422_with_diagnostic(self):
        empty = {"metadata": {}, "nodes": {}, "sources": {}, "exposures": {}}
        with patch("backend.app.api.routes.ingest.get_conn", side_effect=_preview_conn):
            resp = _preview("dbt_manifest", empty, "empty.json")

        assert resp.status_code == 422
        detail = resp.json().get("detail", {})
        diagnostics = detail.get("diagnostics", [])
        codes = [d.get("code", "") for d in diagnostics]
        assert any(
            c in ("NO_SUPPORTED_DBT_RESOURCES", "EMPTY_ASSET_BATCH") for c in codes
        ), f"Expected a resource-not-found diagnostic, got codes: {codes}"

    def test_d5_list_manifest_returns_422(self):
        with patch("backend.app.api.routes.ingest.get_conn", side_effect=_preview_conn):
            resp = _preview("dbt_manifest", [{"node": "x"}], "list.json")

        assert resp.status_code == 422

    def test_d6_dbt_relationships_use_declared_dependency(self):
        with patch("backend.app.api.routes.ingest.get_conn", side_effect=_preview_conn):
            resp = _preview("dbt_manifest", DBT_FIXTURE, "manifest.json")

        normalized = resp.json()["normalized"]
        for rel in normalized["relationships"]:
            assert rel["edge_type"] == "declared_dependency", (
                f"dbt relationships must use 'declared_dependency', got {rel['edge_type']!r}"
            )

    def test_d7_model_carries_column_metadata(self):
        """The model asset must include order_id and amount column metadata."""
        with patch("backend.app.api.routes.ingest.get_conn", side_effect=_preview_conn):
            resp = _preview("dbt_manifest", DBT_FIXTURE, "manifest.json")

        normalized = resp.json()["normalized"]
        model_assets = [a for a in normalized["assets"] if a.get("type") == "model"]
        assert model_assets, "Expected at least one model-type asset"
        col_names = [c["name"] for c in model_assets[0]["metadata"].get("columns", [])]
        assert "order_id" in col_names, f"Expected order_id in columns, got {col_names}"
        assert "amount" in col_names,   f"Expected amount in columns, got {col_names}"

    def test_d8_unauthenticated_returns_401(self):
        resp = client.post(
            "/api/v1/ingest/preview",
            json={"kind": "dbt_manifest", "content": DBT_FIXTURE, "filename": "manifest.json"},
        )
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# COMMIT PATH
# ═══════════════════════════════════════════════════════════════════════════════

class TestCommitPath:

    def test_c1_sql_file_commit_returns_ok_with_counts(self):
        # demo_revenue.sql → 4 assets (file + target + 2 sources) + 2 relationships
        with patch(
            "backend.app.api.routes.ingest.get_conn",
            side_effect=lambda: _commit_conn(num_assets=4, num_relationships=2),
        ):
            resp = _commit("sql_file", SQL_FIXTURE, "demo_revenue.sql")

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["ok"] is True
        assert body["replayed"] is False
        assert body["summary"]["persisted_assets"] >= 3
        assert body["summary"]["persisted_relationships"] >= 2

    def test_c2_dbt_manifest_commit_returns_ok_with_counts(self):
        with patch(
            "backend.app.api.routes.ingest.get_conn",
            side_effect=lambda: _commit_conn(num_assets=3, num_relationships=2),
        ):
            resp = _commit("dbt_manifest", DBT_FIXTURE, "manifest.json")

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["ok"] is True
        assert body["summary"]["persisted_assets"] == 3
        assert body["summary"]["persisted_relationships"] == 2

    def test_c3_idempotent_replay_returns_replayed_true(self):
        """Second commit with same idempotency_key returns replayed=True."""
        key = str(uuid.uuid4())

        # Compute the real content hash the route will use
        from ingestion.static_files import parse_static_file
        result = parse_static_file("sql_file", SQL_FIXTURE, filename="demo_revenue.sql")
        content_hash = result.payload["provenance"]["content_sha256"]

        call_n: dict[str, int] = {"n": 0}

        @contextmanager
        def _alternating():
            call_n["n"] += 1
            if call_n["n"] == 1:
                # First call: new run — full commit rows
                yield _Conn(_Cursor(rows=_commit_rows(4, 2)))
            else:
                # Second call: existing run found on idempotency check
                # fetchone sequence:
                #   [0] to_regclass → {"import_run": "import_run"}
                #   [1] SELECT idempotency → existing row (hash matches) → replayed
                yield _Conn(_Cursor(rows=[
                    {"import_run": "import_run"},
                    {
                        "id": str(uuid.uuid4()),
                        "content_sha256": content_hash,
                        "result_summary": {"assets": 4, "relationships": 2},
                        "status": "COMMITTED",
                    },
                ]))

        with patch("backend.app.api.routes.ingest.get_conn", side_effect=_alternating):
            resp1 = _commit("sql_file", SQL_FIXTURE, "demo_revenue.sql", idempotency_key=key)
            resp2 = _commit("sql_file", SQL_FIXTURE, "demo_revenue.sql", idempotency_key=key)

        assert resp1.json()["replayed"] is False
        assert resp2.json()["replayed"] is True

    def test_c4_different_content_same_key_returns_409(self):
        """Reusing a key for different content must return 409 Conflict."""
        key = str(uuid.uuid4())
        wrong_hash = "a" * 64  # will not match the computed hash for SQL_FIXTURE

        @contextmanager
        def _conflict_conn():
            # fetchone sequence:
            #   [0] to_regclass → {"import_run": "import_run"}
            #   [1] SELECT idempotency → existing row with DIFFERENT hash → 409
            yield _Conn(_Cursor(rows=[
                {"import_run": "import_run"},
                {
                    "id": str(uuid.uuid4()),
                    "content_sha256": wrong_hash,  # mismatch → 409
                    "result_summary": {},
                    "status": "COMMITTED",
                },
            ]))

        with patch("backend.app.api.routes.ingest.get_conn", side_effect=_conflict_conn):
            resp = _commit("sql_file", SQL_FIXTURE, "demo_revenue.sql", idempotency_key=key)

        assert resp.status_code == 409

    def test_c5_commit_without_migration_returns_503(self):
        """When import_run table is absent commit must fail closed with 503."""
        with patch("backend.app.api.routes.ingest.get_conn", side_effect=_no_migration_conn):
            resp = _commit("sql_file", SQL_FIXTURE, "demo_revenue.sql")

        assert resp.status_code == 503


# ═══════════════════════════════════════════════════════════════════════════════
# EVIDENCE CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

class TestEvidenceClassification:

    def test_e1_all_static_relationships_carry_declared_metadata_class(self):
        """
        All relationships in normalized static-file payloads must have
        evidence_class=DECLARED_METADATA — never RUNTIME_POSITIVE.
        """
        with patch("backend.app.api.routes.ingest.get_conn", side_effect=_preview_conn):
            sql_resp = _preview("sql_file", SQL_FIXTURE, "demo_revenue.sql")
            dbt_resp = _preview("dbt_manifest", DBT_FIXTURE, "manifest.json")

        for label, resp in [("sql_file", sql_resp), ("dbt_manifest", dbt_resp)]:
            normalized = resp.json()["normalized"]
            for rel in normalized["relationships"]:
                evidence_class = rel.get("evidence_class")
                assert evidence_class == "DECLARED_METADATA", (
                    f"[{label}] relationship evidence_class must be DECLARED_METADATA, "
                    f"got {evidence_class!r}"
                )

    def test_e2_no_runtime_evidence_in_static_import(self):
        """Static import must never produce runtime evidence records."""
        with patch("backend.app.api.routes.ingest.get_conn", side_effect=_preview_conn):
            resp = _preview("sql_file", SQL_FIXTURE, "demo_revenue.sql")

        normalized = resp.json()["normalized"]
        for ev in normalized.get("evidence", []):
            ev_type = ev.get("type", "")
            assert ev_type not in ("RUNTIME_POSITIVE", "RUNTIME_NEGATIVE_EVALUATION"), (
                f"Static import must not produce runtime evidence, got type={ev_type!r}"
            )
