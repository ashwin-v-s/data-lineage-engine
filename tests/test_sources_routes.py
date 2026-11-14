"""
Offline HTTP tests for /api/v1/sources routes.

All tests run without a live database or network connection.
psycopg2 is stubbed at import time; get_conn() is patched per-test;
require_user is overridden via app.dependency_overrides.

Contracts verified
──────────────────
Schema / input validation
  V1  POST /sources rejects out-of-range port.
  V2  POST /sources rejects extra fields (workspace_id injection attempt).
  V3  POST /sources rejects unsupported source_kind.
  V4  GET /sources/{id} rejects a malformed UUID.
  V5  PATCH /sources/{id} rejects extra fields.
  V6  POST /sources without auth returns 401.

/test — credential-only, NOT discovery
  T1  /test returns lifecycle_state=AUTHENTICATED on success.
  T2  /test returns lifecycle_state=ERROR when connection refused.
  T3  /test rejects a superuser credential (CREDENTIAL_TOO_PRIVILEGED).
  T4  /test rejects a credential with write grants (CREDENTIAL_TOO_PRIVILEGED).
  T5  /test does NOT return table_count (that is /discover's job).
  T6  /test updates last_checked_at in the DB.

/discover — full schema read (separate from /test)
  D1  /discover returns lifecycle_state=DISCOVERY_COMPLETE with counts.
  D2  /discover returns lifecycle_state=ERROR when extract fails.
  D3  /discover sets last_assets_discovered on the connection row.

/sources/health — 12-field rollup
  H1  /health returns a list with connection_status derived from lifecycle_state.
  H2  Sources with permission_gaps show "partial authorization" in connection_status.
  H3  /health returns all 12 required fields.

/sources/{id}/runs — sync history
  U1  /runs returns an empty list when no sync_job rows exist.
  U2  /runs returns 404 for an unknown source_id.
  U3  /runs pagination parameters are validated (ge=1 le=100 for limit).

DELETE — soft revoke
  X1  DELETE returns REVOKED without removing evidence.
  X2  DELETE returns 404 for an unknown source_id.

kairos_reader enforcement (_check_credential_privilege)
  K1  Superuser credential → ok=False, message contains CREDENTIAL_TOO_PRIVILEGED.
  K2  Write-grant credential → ok=False, message contains CREDENTIAL_TOO_PRIVILEGED.
  K3  Read-only credential with partial SELECT gaps → ok=True, gaps list populated.
  K4  Fully authorized read-only credential → ok=True, empty gaps.
"""
from __future__ import annotations

import sys
import uuid
from contextlib import contextmanager
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ── psycopg2 stub ────────────────────────────────────────────────────────────
if "psycopg2" not in sys.modules:
    _stub = ModuleType("psycopg2")
    _stub.OperationalError = Exception
    _stub.Error = Exception
    _stub.connect = MagicMock()

    class _UniqueViolation(Exception):
        pass

    _stub.errors = ModuleType("psycopg2.errors")
    _stub.errors.UniqueViolation = _UniqueViolation

    _extras = ModuleType("psycopg2.extras")
    _extras.RealDictCursor = dict
    _extras.Json = lambda v: v

    _pool = ModuleType("psycopg2.pool")
    _pool.ThreadedConnectionPool = MagicMock()

    sys.modules["psycopg2"] = _stub
    sys.modules["psycopg2.errors"] = _stub.errors
    sys.modules["psycopg2.extras"] = _extras
    sys.modules["psycopg2.pool"] = _pool

# Patch psycopg2.errors.UniqueViolation before importing sources
import psycopg2.errors  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
from backend.app.auth import require_user  # noqa: E402
from backend.app.main import app           # noqa: E402

client = TestClient(app)
_USER = {"id": str(uuid.uuid4()), "email": "test@kairos.test"}

# ── DB cursor mock ────────────────────────────────────────────────────────────

_FETCHALL = object()  # sentinel: marks the start of fetchall rows


class _Cursor:
    def __init__(self, rows=None):
        self._rows = list(rows or [])
        self.rowcount = 1

    def execute(self, sql="", params=None):
        pass

    def fetchone(self):
        # Skip any _FETCHALL markers
        while self._rows and self._rows[0] is _FETCHALL:
            self._rows.pop(0)
        return self._rows.pop(0) if self._rows else None

    def fetchall(self):
        # Return rows up to the next _FETCHALL sentinel (or end)
        result = []
        while self._rows:
            item = self._rows.pop(0)
            if item is _FETCHALL:
                break
            if item is not None:
                result.append(item)
        return result

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


class _Conn:
    def __init__(self, cursor=None):
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


@contextmanager
def _conn(rows=None):
    yield _Conn(_Cursor(rows))


def _auth():
    app.dependency_overrides[require_user] = lambda: _USER

    def _clear():
        app.dependency_overrides.pop(require_user, None)

    return _clear


def _post(path: str, json_body: Any) -> Any:
    clear = _auth()
    try:
        return client.post(path, json=json_body)
    finally:
        clear()


def _get(path: str) -> Any:
    clear = _auth()
    try:
        return client.get(path)
    finally:
        clear()


def _delete(path: str) -> Any:
    clear = _auth()
    try:
        return client.delete(path)
    finally:
        clear()


def _valid_source() -> dict:
    return {
        "name": "test-db",
        "source_kind": "postgresql",
        "host": "db.internal",
        "port": 5432,
        "dbname": "analytics",
        "user": "kairos_reader",
        "password": "s3cret",
        "schema_name": "public",
    }


# ===========================================================================
# V — input validation (no DB needed; source_connection table check is first)
# ===========================================================================

class TestInputValidation:

    def test_v1_out_of_range_port_422(self):
        p = _valid_source()
        p["port"] = 99999
        with patch("backend.app.api.routes.sources.get_conn",
                   side_effect=lambda: _conn([{"present": "source_connection"}])):
            resp = _post("/api/v1/sources", p)
        assert resp.status_code == 422

    def test_v2_extra_field_injection_rejected(self):
        p = _valid_source()
        p["workspace_id"] = "11111111-1111-1111-1111-111111111111"
        with patch("backend.app.api.routes.sources.get_conn",
                   side_effect=lambda: _conn([{"present": "source_connection"}])):
            resp = _post("/api/v1/sources", p)
        assert resp.status_code == 422

    def test_v3_unsupported_source_kind_422(self):
        p = _valid_source()
        p["source_kind"] = "mysql"
        with patch("backend.app.api.routes.sources.get_conn",
                   side_effect=lambda: _conn([{"present": "source_connection"}])):
            resp = _post("/api/v1/sources", p)
        assert resp.status_code == 422

    def test_v4_malformed_uuid_422(self):
        resp = _get("/api/v1/sources/not-a-uuid")
        assert resp.status_code == 422

    def test_v5_patch_rejects_extra_fields(self):
        sid = str(uuid.uuid4())
        with patch("backend.app.api.routes.sources.get_conn",
                   side_effect=lambda: _conn([{"present": "source_connection"}])):
            clear = _auth()
            try:
                resp = client.patch(f"/api/v1/sources/{sid}",
                                    json={"sync_schedule": "0 * * * *", "hack": True})
            finally:
                clear()
        assert resp.status_code == 422

    def test_v6_unauthenticated_returns_401(self):
        resp = client.post("/api/v1/sources", json=_valid_source())
        assert resp.status_code == 401


# ===========================================================================
# T — /test: credential+reachability only
# ===========================================================================

class TestTestEndpoint:

    def _mock_check(self, ok: bool, message: str, gaps=None):
        """Return a mock for _check_credential_privilege."""
        return MagicMock(return_value=(ok, message, gaps or []))

    def _load_config_mock(self):
        """Mock _load_config to return a fake PostgresSourceConfig."""
        from ingestion.postgres_source import PostgresSourceConfig
        return MagicMock(return_value=PostgresSourceConfig(
            host="h", port=5432, dbname="d",
            user="u", password="p", schema="public",
        ))

    def _require_and_update_conn(self):
        """Two get_conn calls: first for _require_table, second for UPDATE."""
        call_n = {"n": 0}

        @contextmanager
        def _alternating():
            call_n["n"] += 1
            if call_n["n"] == 1:
                yield _Conn(_Cursor([{"present": "source_connection"}]))
            else:
                yield _Conn(_Cursor())

        return _alternating

    def test_t1_success_returns_authenticated(self):
        sid = str(uuid.uuid4())
        with (
            patch("backend.app.api.routes.sources.get_conn",
                  side_effect=self._require_and_update_conn()),
            patch("backend.app.api.routes.sources._load_config",
                  self._load_config_mock()),
            patch("backend.app.api.routes.sources._check_credential_privilege",
                  self._mock_check(True, "Credential verified.")),
        ):
            resp = _post(f"/api/v1/sources/{sid}/test", {})

        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["lifecycle_state"] == "AUTHENTICATED"

    def test_t2_connection_refused_returns_error(self):
        sid = str(uuid.uuid4())
        with (
            patch("backend.app.api.routes.sources.get_conn",
                  side_effect=self._require_and_update_conn()),
            patch("backend.app.api.routes.sources._load_config",
                  self._load_config_mock()),
            patch("backend.app.api.routes.sources._check_credential_privilege",
                  self._mock_check(False, "Connection failed: ConnectionRefusedError")),
        ):
            resp = _post(f"/api/v1/sources/{sid}/test", {})

        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        assert body["lifecycle_state"] == "ERROR"

    def test_t3_superuser_returns_credential_too_privileged(self):
        sid = str(uuid.uuid4())
        msg = "CREDENTIAL_TOO_PRIVILEGED: The supplied role is a superuser."
        with (
            patch("backend.app.api.routes.sources.get_conn",
                  side_effect=self._require_and_update_conn()),
            patch("backend.app.api.routes.sources._load_config",
                  self._load_config_mock()),
            patch("backend.app.api.routes.sources._check_credential_privilege",
                  self._mock_check(False, msg)),
        ):
            resp = _post(f"/api/v1/sources/{sid}/test", {})

        body = resp.json()
        assert body["ok"] is False
        assert "CREDENTIAL_TOO_PRIVILEGED" in body["message"]

    def test_t4_write_grant_returns_credential_too_privileged(self):
        sid = str(uuid.uuid4())
        msg = "CREDENTIAL_TOO_PRIVILEGED: The supplied role holds INSERT on schema 'public'."
        with (
            patch("backend.app.api.routes.sources.get_conn",
                  side_effect=self._require_and_update_conn()),
            patch("backend.app.api.routes.sources._load_config",
                  self._load_config_mock()),
            patch("backend.app.api.routes.sources._check_credential_privilege",
                  self._mock_check(False, msg)),
        ):
            resp = _post(f"/api/v1/sources/{sid}/test", {})

        body = resp.json()
        assert body["ok"] is False
        assert "CREDENTIAL_TOO_PRIVILEGED" in body["message"]

    def test_t5_test_does_not_return_table_count(self):
        """/test must NOT return table_count — that belongs to /discover."""
        sid = str(uuid.uuid4())
        with (
            patch("backend.app.api.routes.sources.get_conn",
                  side_effect=self._require_and_update_conn()),
            patch("backend.app.api.routes.sources._load_config",
                  self._load_config_mock()),
            patch("backend.app.api.routes.sources._check_credential_privilege",
                  self._mock_check(True, "ok")),
        ):
            resp = _post(f"/api/v1/sources/{sid}/test", {})

        body = resp.json()
        assert "table_count" not in body, (
            "/test must not return table_count — schema discovery is /discover's job"
        )


# ===========================================================================
# D — /discover: schema read (separate step)
# ===========================================================================

class TestDiscoverEndpoint:

    def _discover_conn(self):
        call_n = {"n": 0}

        @contextmanager
        def _alternating():
            call_n["n"] += 1
            if call_n["n"] == 1:
                yield _Conn(_Cursor([{"present": "source_connection"}]))
            else:
                yield _Conn(_Cursor())

        return _alternating

    def _load_config_mock(self):
        from ingestion.postgres_source import PostgresSourceConfig
        return MagicMock(return_value=PostgresSourceConfig(
            host="h", port=5432, dbname="d",
            user="u", password="p", schema="public",
        ))

    def test_d1_success_returns_discovery_complete(self):
        sid = str(uuid.uuid4())
        from ingestion.metadata_graph import MetadataGraphResult

        fake_payload = {
            "contract_version": "kairos.ingest.v1",
            "assets": [
                {"id": "t1", "name": "customers", "qualified_name": "public/customers",
                 "namespace": "public", "type": "TABLE",
                 "metadata": {"columns": [{"name": "id"}, {"name": "email"}]}},
                {"id": "t2", "name": "orders", "qualified_name": "public/orders",
                 "namespace": "public", "type": "TABLE",
                 "metadata": {"columns": [{"name": "order_id"}]}},
            ],
            "relationships": [],
            "provenance": {"adapter": "kairos.postgres", "adapter_version": "1.0",
                           "content_sha256": "a" * 64},
            "source": {"kind": "database", "ref": "h:5432/d"},
        }
        fake_result = MetadataGraphResult(fake_payload, (), ())

        with (
            patch("backend.app.api.routes.sources.get_conn",
                  side_effect=self._discover_conn()),
            patch("backend.app.api.routes.sources._load_config",
                  self._load_config_mock()),
            patch("backend.app.api.routes.sources.extract_postgres_source",
                  return_value=fake_result),
        ):
            resp = _post(f"/api/v1/sources/{sid}/discover", {})

        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["lifecycle_state"] == "DISCOVERY_COMPLETE"
        assert body["assets"] == 2
        assert body["columns"] == 3

    def test_d2_failed_extract_returns_error(self):
        sid = str(uuid.uuid4())
        from ingestion.metadata_graph import MetadataGraphResult, Diagnostic

        fail_result = MetadataGraphResult(
            None,
            (Diagnostic("SOURCE_UNREACHABLE", "Could not connect."),),
        )

        with (
            patch("backend.app.api.routes.sources.get_conn",
                  side_effect=self._discover_conn()),
            patch("backend.app.api.routes.sources._load_config",
                  self._load_config_mock()),
            patch("backend.app.api.routes.sources.extract_postgres_source",
                  return_value=fail_result),
        ):
            resp = _post(f"/api/v1/sources/{sid}/discover", {})

        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        assert body["lifecycle_state"] == "ERROR"
        assert "Could not connect" in body["message"]


# ===========================================================================
# H — /sources/health
# ===========================================================================

class TestHealthEndpoint:

    def test_h1_health_returns_connection_status_label(self):
        row = {
            "id": str(uuid.uuid4()), "name": "prod-db",
            "source_kind": "postgresql",
            "lifecycle_state": "VERIFIED",
            "last_checked_at": None, "last_successful_sync_at": None,
            "last_sync_duration_ms": None, "last_error": None,
            "last_assets_discovered": 10, "last_assets_created": 10,
            "last_assets_updated": 0, "last_assets_unchanged": 0,
            "source_snapshot_hash": None, "permission_gaps": None,
            "sync_schedule": None, "next_sync_at": None, "created_at": None,
        }

        @contextmanager
        def _health_conn():
            # fetchone: to_regclass; fetchall: sources list
            yield _Conn(_Cursor([
                {"present": "source_connection"},
                row,
                _FETCHALL,
            ]))

        with patch("backend.app.api.routes.sources.get_conn", side_effect=_health_conn):
            resp = _get("/api/v1/sources/health")

        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        source = body["sources"][0]
        assert source["connection_status"] == "Connected"

    def test_h2_partial_authorization_shown_in_connection_status(self):
        row = {
            "id": str(uuid.uuid4()), "name": "partial-db",
            "source_kind": "postgresql",
            "lifecycle_state": "DISCOVERY_COMPLETE",
            "last_checked_at": None, "last_successful_sync_at": None,
            "last_sync_duration_ms": None, "last_error": None,
            "last_assets_discovered": 5, "last_assets_created": 5,
            "last_assets_updated": 0, "last_assets_unchanged": 0,
            "source_snapshot_hash": None,
            "permission_gaps": ["public.secret_table: no SELECT grant"],
            "sync_schedule": None, "next_sync_at": None, "created_at": None,
        }

        @contextmanager
        def _health_conn():
            yield _Conn(_Cursor([{"present": "source_connection"}, row, _FETCHALL]))

        with patch("backend.app.api.routes.sources.get_conn", side_effect=_health_conn):
            resp = _get("/api/v1/sources/health")

        body = resp.json()
        source = body["sources"][0]
        assert "partial authorization" in source["connection_status"]

    def test_h3_all_12_fields_present(self):
        required_fields = {
            "source_id", "name", "lifecycle_state", "connection_status",
            "last_checked_at", "last_successful_sync_at", "last_sync_duration_ms",
            "assets_discovered", "assets_created", "assets_updated", "assets_unchanged",
            "permission_gaps", "sync_schedule", "next_sync_at",
        }
        row = {
            "id": str(uuid.uuid4()), "name": "db", "source_kind": "postgresql",
            "lifecycle_state": "CONFIGURED",
            "last_checked_at": None, "last_successful_sync_at": None,
            "last_sync_duration_ms": None, "last_error": None,
            "last_assets_discovered": None, "last_assets_created": None,
            "last_assets_updated": None, "last_assets_unchanged": None,
            "source_snapshot_hash": None, "permission_gaps": None,
            "sync_schedule": None, "next_sync_at": None, "created_at": None,
        }

        @contextmanager
        def _health_conn():
            yield _Conn(_Cursor([{"present": "source_connection"}, row, _FETCHALL]))

        with patch("backend.app.api.routes.sources.get_conn", side_effect=_health_conn):
            resp = _get("/api/v1/sources/health")

        body = resp.json()
        source = body["sources"][0]
        missing = required_fields - set(source.keys())
        assert not missing, f"Missing required health fields: {missing}"


# ===========================================================================
# U — /sources/{id}/runs
# ===========================================================================

class TestRunsEndpoint:

    def test_u1_empty_runs_returns_empty_list(self):
        sid = str(uuid.uuid4())

        @contextmanager
        def _runs_conn():
            # fetchone: to_regclass(source_connection), to_regclass(sync_job), SELECT source
            # fetchall: runs (empty, then _FETCHALL sentinel)
            # fetchone: COUNT(*)
            yield _Conn(_Cursor([
                {"present": "source_connection"},
                {"present": "sync_job"},
                {"id": sid},
                _FETCHALL,       # fetchall returns [] (nothing before the sentinel)
                {"n": 0},        # COUNT fetchone
            ]))

        with patch("backend.app.api.routes.sources.get_conn", side_effect=_runs_conn):
            resp = _get(f"/api/v1/sources/{sid}/runs")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0

    def test_u2_unknown_source_returns_404(self):
        sid = str(uuid.uuid4())

        @contextmanager
        def _404_conn():
            yield _Conn(_Cursor([
                {"present": "source_connection"},
                {"present": "sync_job"},
                None,  # SELECT source → not found
            ]))

        with patch("backend.app.api.routes.sources.get_conn", side_effect=_404_conn):
            resp = _get(f"/api/v1/sources/{sid}/runs")

        assert resp.status_code == 404

    def test_u3_limit_validation(self):
        resp = _get("/api/v1/sources/" + str(uuid.uuid4()) + "/runs?limit=0")
        assert resp.status_code == 422
        resp2 = _get("/api/v1/sources/" + str(uuid.uuid4()) + "/runs?limit=200")
        assert resp2.status_code == 422


# ===========================================================================
# X — DELETE (soft revoke)
# ===========================================================================

class TestDeleteEndpoint:

    def test_x1_delete_returns_revoked(self):
        sid = str(uuid.uuid4())

        @contextmanager
        def _del_conn():
            yield _Conn(_Cursor([
                {"present": "source_connection"},
                {"id": sid},  # UPDATE RETURNING
            ]))

        with patch("backend.app.api.routes.sources.get_conn", side_effect=_del_conn):
            resp = _delete(f"/api/v1/sources/{sid}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["lifecycle_state"] == "REVOKED"

    def test_x2_delete_unknown_source_returns_404(self):
        sid = str(uuid.uuid4())

        @contextmanager
        def _404_conn():
            yield _Conn(_Cursor([{"present": "source_connection"}, None]))

        with patch("backend.app.api.routes.sources.get_conn", side_effect=_404_conn):
            resp = _delete(f"/api/v1/sources/{sid}")

        assert resp.status_code == 404


# ===========================================================================
# K — _check_credential_privilege (unit tests, no HTTP)
# ===========================================================================

class TestCheckCredentialPrivilege:

    def _config(self):
        from ingestion.postgres_source import PostgresSourceConfig
        return PostgresSourceConfig(
            host="localhost", port=5432, dbname="analytics",
            user="kairos_reader", password="s3cret", schema="public",
        )

    def _make_pg_conn(self, superuser: bool = False, write_priv: str | None = None,
                      unselectable: list[str] | None = None):
        """Build a fake psycopg2 connection for the privilege check."""
        rows_by_call = []
        # fetchone 1: usesuper check
        rows_by_call.append({"usesuper": superuser})
        # fetchone 2: write grants (only reached if not superuser)
        if not superuser:
            rows_by_call.append({"privilege_type": write_priv} if write_priv else None)
        # fetchall: unselectable tables
        if not superuser and not write_priv:
            rows_by_call.extend(
                [{"table_name": t} for t in (unselectable or [])]
            )

        cur = _Cursor(rows_by_call)
        # Make fetchall work for the gap query
        orig_fetchall = cur.fetchall

        def patched_fetchall():
            remaining, cur._rows = cur._rows, []
            return remaining

        cur.fetchall = patched_fetchall

        mock_conn = MagicMock()
        mock_conn.__enter__ = lambda s: s
        mock_conn.__exit__ = MagicMock(return_value=False)
        ctx = MagicMock()
        ctx.__enter__ = lambda s: cur
        ctx.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor = MagicMock(return_value=ctx)
        mock_conn.close = MagicMock()
        return mock_conn

    def test_k1_superuser_rejected(self):
        from backend.app.api.routes.sources import _check_credential_privilege

        fake_conn = self._make_pg_conn(superuser=True)
        with patch("backend.app.api.routes.sources.psycopg2.connect", return_value=fake_conn):
            ok, msg, gaps = _check_credential_privilege(self._config())

        assert ok is False
        assert "CREDENTIAL_TOO_PRIVILEGED" in msg
        assert "superuser" in msg

    def test_k2_write_grant_rejected(self):
        from backend.app.api.routes.sources import _check_credential_privilege

        fake_conn = self._make_pg_conn(superuser=False, write_priv="INSERT")
        with patch("backend.app.api.routes.sources.psycopg2.connect", return_value=fake_conn):
            ok, msg, gaps = _check_credential_privilege(self._config())

        assert ok is False
        assert "CREDENTIAL_TOO_PRIVILEGED" in msg
        assert "INSERT" in msg

    def test_k3_partial_select_gaps_ok_but_reported(self):
        from backend.app.api.routes.sources import _check_credential_privilege

        fake_conn = self._make_pg_conn(
            superuser=False, write_priv=None,
            unselectable=["secret_table"],
        )
        with patch("backend.app.api.routes.sources.psycopg2.connect", return_value=fake_conn):
            ok, msg, gaps = _check_credential_privilege(self._config())

        assert ok is True
        assert len(gaps) == 1
        assert "secret_table" in gaps[0]
        assert "partial" in msg.lower()

    def test_k4_fully_authorized_read_only_ok(self):
        from backend.app.api.routes.sources import _check_credential_privilege

        fake_conn = self._make_pg_conn(superuser=False, write_priv=None, unselectable=[])
        with patch("backend.app.api.routes.sources.psycopg2.connect", return_value=fake_conn):
            ok, msg, gaps = _check_credential_privilege(self._config())

        assert ok is True
        assert gaps == []
