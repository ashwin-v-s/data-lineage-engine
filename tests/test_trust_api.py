"""Offline contract tests for the trust center and quality scorecard.

No database contact: connections are fakes that answer scripted rows, and the
unprovisioned path (table missing) is exercised through the to_regclass guard.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app import db as dbmod
from backend.app.api.routes import membership as membership_routes
from backend.app.api.routes import quality as quality_routes
from backend.app.api.routes import trust as trust_routes
from backend.app.auth import require_user
from backend.app.main import app

USER = {"id": "11111111-1111-4111-8111-aaaaaaaaaaaa", "email": "steward@example.com"}
WORKSPACE = "11111111-1111-4111-8111-111111111111"
DATASET_ID = "44444444-4444-4444-8444-dddddddddddd"
CERT_ID = "55555555-5555-4555-8555-eeeeeeeeeeee"
COMMENT_ID = "66666666-6666-4666-8666-ffffffffffff"
NOW = "2026-11-26T09:00:00.000000Z"


class _Cursor:
    def __init__(self, conn):
        self.conn = conn
        self.stmts: list[tuple[str, tuple | None]] = []
        self.rowcount = 0
        self._rows: list = []

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, sql, params=None):
        self.stmts.append((" ".join(sql.split()), params))
        for needle, fn in self.conn.handlers:
            if needle in sql:
                self._rows = fn(self.stmts, params) or []
                return
        raise AssertionError(f"Unexpected SQL in trust test: {sql[:160]}")

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class _Conn:
    def __init__(self, *handlers):
        self.handlers = list(handlers)
        self.cursor_obj: _Cursor | None = None

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def cursor(self, *args, **kwargs):
        self.cursor_obj = _Cursor(self)
        return self.cursor_obj

    def commit(self):
        pass

    def rollback(self):
        pass


class _Row(dict):
    """A row readable by column name *and* by position.

    The trust route reads ``row["relation"]`` while the shared membership guard
    reads ``row[0]``; production uses RealDictRow, which is not positional, but
    the fake has to satisfy both call sites.
    """

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


def _regclass(table: str | None):
    def handler(stmts, params):
        return [_Row(relation=table)]

    return ("to_regclass", handler)


def _role(role: str):
    def handler(stmts, params):
        return [(role,)]

    return ("SELECT role", handler)


def _cert_row(state="CERTIFIED", expires_at=None):
    return {
        "id": CERT_ID,
        "dataset_id": DATASET_ID,
        "dataset_name": "fct_daily_revenue",
        "asset_type": "MODEL",
        "qualified_name": "analytics.fct_daily_revenue",
        "note": "Reviewed against the revenue definition.",
        "certified_by": USER["id"],
        "certified_by_label": USER["email"],
        "expires_at": expires_at,
        "created_at": NOW,
        "updated_at": NOW,
        "state": state,
    }


def _comment_row(parent_id=None, resolved_at=None):
    return {
        "id": COMMENT_ID,
        "dataset_id": DATASET_ID,
        "parent_id": parent_id,
        "author_id": USER["id"],
        "author_label": USER["email"],
        "body": "Which definition of net revenue is authoritative?",
        "resolved_at": resolved_at,
        "resolved_by": USER["id"] if resolved_at else None,
        "created_at": NOW,
    }


@pytest.fixture
def workspace_scope():
    token = dbmod.set_workspace_id(WORKSPACE)
    try:
        yield
    finally:
        dbmod.reset_workspace_id(token)


@pytest.fixture
def client(workspace_scope):
    app.dependency_overrides[require_user] = lambda: USER
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(require_user, None)


def _use(monkeypatch, module, conn):
    monkeypatch.setattr(module, "get_conn", lambda: conn)
    monkeypatch.setattr(membership_routes, "get_conn", lambda: conn)
    return conn


def _dataset(stmts, params):
    return [{"id": DATASET_ID, "name": "fct_daily_revenue"}]


# ── Provisioning guard ───────────────────────────────────────────────────────

def test_overview_unprovisioned_returns_503(client, monkeypatch):
    _use(monkeypatch, trust_routes, _Conn(_regclass(None)))
    response = client.get("/api/v1/trust/overview")
    assert response.status_code == 503
    assert "0019" in response.text


def test_certify_unprovisioned_returns_503(client, monkeypatch):
    _use(monkeypatch, trust_routes, _Conn(_regclass(None)))
    response = client.put(f"/api/v1/trust/assets/{DATASET_ID}/certification", json={"note": "Reviewed"})
    assert response.status_code == 503


# ── Certification ────────────────────────────────────────────────────────────

def test_editor_certifies_asset(client, monkeypatch):
    conn = _use(
        monkeypatch,
        trust_routes,
        _Conn(
            _regclass("asset_certification"),
            _role("editor"),
            ("SELECT id::text AS id, name FROM dataset", _dataset),
            ("INSERT INTO asset_certification", lambda s, p: [{"id": CERT_ID}]),
            ("FROM   asset_certification c", lambda s, p: [_cert_row()]),
        ),
    )
    response = client.put(
        f"/api/v1/trust/assets/{DATASET_ID}/certification",
        json={"note": "  Reviewed against the revenue definition.  "},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["certification"]["state"] == "CERTIFIED"
    insert_params = [p for sql, p in conn.cursor_obj.stmts if "INSERT INTO asset_certification" in sql][0]
    assert insert_params[0] == DATASET_ID
    assert insert_params[1] == "Reviewed against the revenue definition."
    assert insert_params[2] == USER["id"]
    assert insert_params[3] == USER["email"]
    assert insert_params[4] is None


def test_viewer_cannot_certify(client, monkeypatch):
    _use(monkeypatch, trust_routes, _Conn(_regclass("asset_certification"), _role("viewer")))
    response = client.put(f"/api/v1/trust/assets/{DATASET_ID}/certification", json={})
    assert response.status_code == 403


def test_expiry_must_include_timezone(client, monkeypatch):
    _use(monkeypatch, trust_routes, _Conn(_regclass("asset_certification"), _role("editor")))
    response = client.put(
        f"/api/v1/trust/assets/{DATASET_ID}/certification",
        json={"expires_at": "2027-01-01T00:00:00"},
    )
    assert response.status_code == 422
    assert "timezone" in response.text


def test_revoke_reports_missing_certification(client, monkeypatch):
    _use(
        monkeypatch,
        trust_routes,
        _Conn(
            _regclass("asset_certification"),
            _role("editor"),
            ("SELECT id::text AS id, name FROM dataset", _dataset),
            ("DELETE FROM asset_certification", lambda s, p: []),
        ),
    )
    response = client.delete(f"/api/v1/trust/assets/{DATASET_ID}/certification")
    assert response.status_code == 404


def test_certification_list_reports_read_time_state(client, monkeypatch):
    _use(
        monkeypatch,
        trust_routes,
        _Conn(
            _regclass("asset_certification"),
            (
                "FROM   asset_certification c",
                lambda s, p: [_cert_row(), _cert_row(state="EXPIRING"), _cert_row(state="EXPIRED")],
            ),
        ),
    )
    response = client.get("/api/v1/trust/certifications?state=expiring")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["certifications"][0]["state"] == "EXPIRING"


# ── Discussions ──────────────────────────────────────────────────────────────

def test_member_opens_thread(client, monkeypatch):
    conn = _use(
        monkeypatch,
        trust_routes,
        _Conn(
            _regclass("asset_discussion"),
            ("SELECT id::text AS id, name FROM dataset", _dataset),
            ("INSERT INTO asset_discussion", lambda s, p: [_comment_row()]),
        ),
    )
    response = client.post(
        f"/api/v1/trust/assets/{DATASET_ID}/discussion",
        json={"body": "  Which definition of net revenue is authoritative?  "},
    )
    assert response.status_code == 201
    assert response.json()["comment"]["parent_id"] is None
    insert_params = [p for sql, p in conn.cursor_obj.stmts if "INSERT INTO asset_discussion" in sql][0]
    assert insert_params[0] == DATASET_ID
    assert insert_params[1] is None
    assert insert_params[2] == USER["id"]
    assert insert_params[4] == "Which definition of net revenue is authoritative?"


def test_api_key_principal_cannot_comment(workspace_scope, monkeypatch):
    app.dependency_overrides[require_user] = lambda: {"id": "api-key:abc", "auth": "api_key"}
    _use(monkeypatch, trust_routes, _Conn(_regclass("asset_discussion")))
    try:
        response = TestClient(app).post(
            f"/api/v1/trust/assets/{DATASET_ID}/discussion", json={"body": "Automated note"}
        )
    finally:
        app.dependency_overrides.pop(require_user, None)
    assert response.status_code == 403


def test_reply_must_target_a_thread_root(client, monkeypatch):
    _use(
        monkeypatch,
        trust_routes,
        _Conn(
            _regclass("asset_discussion"),
            ("SELECT id::text AS id, name FROM dataset", _dataset),
            (
                "SELECT id::text, parent_id::text FROM asset_discussion",
                lambda s, p: [{"id": COMMENT_ID, "parent_id": COMMENT_ID}],
            ),
        ),
    )
    response = client.post(
        f"/api/v1/trust/assets/{DATASET_ID}/discussion",
        json={"body": "A nested reply", "parent_id": COMMENT_ID},
    )
    assert response.status_code == 422
    assert "thread root" in response.text


def test_resolving_a_reply_is_rejected(client, monkeypatch):
    _use(
        monkeypatch,
        trust_routes,
        _Conn(
            _regclass("asset_discussion"),
            _role("editor"),
            (
                "SELECT id::text, parent_id::text, resolved_at FROM asset_discussion",
                lambda s, p: [{"id": COMMENT_ID, "parent_id": "77777777-7777-4777-8777-888888888888", "resolved_at": None}],
            ),
        ),
    )
    response = client.post(f"/api/v1/trust/discussion/{COMMENT_ID}/resolve")
    assert response.status_code == 422


def test_resolving_an_already_resolved_thread_is_a_conflict(client, monkeypatch):
    _use(
        monkeypatch,
        trust_routes,
        _Conn(
            _regclass("asset_discussion"),
            _role("editor"),
            (
                "SELECT id::text, parent_id::text, resolved_at FROM asset_discussion",
                lambda s, p: [{"id": COMMENT_ID, "parent_id": None, "resolved_at": datetime(2026, 11, 20, tzinfo=timezone.utc)}],
            ),
        ),
    )
    response = client.post(f"/api/v1/trust/discussion/{COMMENT_ID}/resolve")
    assert response.status_code == 409


def test_discussion_list_counts_open_threads(client, monkeypatch):
    _use(
        monkeypatch,
        trust_routes,
        _Conn(
            _regclass("asset_discussion"),
            ("SELECT id::text AS id, name FROM dataset", _dataset),
            (
                "FROM   asset_discussion c",
                lambda s, p: [
                    _comment_row(),
                    _comment_row(),
                    {**_comment_row(parent_id=COMMENT_ID), "id": "99999999-9999-4999-8999-aaaaaaaaaaaa"},
                ],
            ),
        ),
    )
    response = client.get(f"/api/v1/trust/assets/{DATASET_ID}/discussion")
    assert response.status_code == 200
    body = response.json()
    assert body["threads"] == 2
    assert body["open_threads"] == 2
    assert body["count"] == 3


# ── Overview ─────────────────────────────────────────────────────────────────

def test_overview_combines_trust_and_quality(client, monkeypatch):
    _use(
        monkeypatch,
        trust_routes,
        _Conn(
            _regclass("asset_certification"),
            _regclass("asset_discussion"),
            _regclass("asset_engagement"),
            (
                "FROM asset_certification",
                lambda s, p: [{"total": 3, "expired": 1, "expiring": 1}],
            ),
            ("FROM dataset", lambda s, p: [{"total": 10, "owned": 7}]),
            (
                "FROM asset_discussion",
                lambda s, p: [{"threads": 4, "open_threads": 2, "comments": 9}],
            ),
            (
                "FROM   asset_engagement e",
                lambda s, p: [{"asset_id": DATASET_ID, "name": "orders", "asset_type": "TABLE", "qualified_name": "raw.orders", "view_count": 12, "last_viewed_at": NOW}],
            ),
            (
                "FROM   quality_assertion a",
                lambda s, p: [{"severity": "HIGH", "status": "PASS"}, {"severity": "HIGH", "status": "FAIL"}],
            ),
            ("to_char(date_trunc", lambda s, p: [{"day": "2026-11-26", "evaluated": 2, "passed": 1, "failed": 1, "skipped": 0, "errored": 0}]),
            ("FROM   dataset d", lambda s, p: [{"count": 8}]),
        ),
    )
    response = client.get("/api/v1/trust/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["certification"] == {
        "certified": 2,
        "expiring_soon": 1,
        "expired": 1,
        "uncertified": 7,
        "coverage": 0.3,
    }
    assert body["ownership"]["coverage"] == 0.7
    assert body["discussion"]["open_threads"] == 2
    assert body["trending"][0]["view_count"] == 12
    assert body["quality"]["summary"]["pass_rate"] == 0.5
    assert body["quality"]["uncovered_assets"] == 8


# ── Quality scorecard endpoint ───────────────────────────────────────────────

def test_scorecard_never_scores_skipped_results(client, monkeypatch):
    _use(
        monkeypatch,
        quality_routes,
        _Conn(
            _regclass("quality_assertion"),
            _regclass("quality_result"),
            (
                "FROM   quality_assertion a",
                lambda s, p: [
                    {"severity": "CRITICAL", "status": "PASS"},
                    {"severity": "MEDIUM", "status": "SKIPPED"},
                    {"severity": "LOW", "status": None},
                ],
            ),
            ("to_char(date_trunc", lambda s, p: []),
            ("FROM   dataset d", lambda s, p: [{"count": 4}]),
        ),
    )
    response = client.get("/api/v1/quality/scorecard?days=7")
    assert response.status_code == 200
    body = response.json()
    assert body["window_days"] == 7
    assert body["summary"]["assertions"] == 3
    assert body["summary"]["evaluated"] == 2
    assert body["summary"]["passing"] == 1
    assert body["summary"]["failing"] == 0
    assert body["summary"]["skipped"] == 1
    assert body["summary"]["unevaluated"] == 1
    # One PASS and zero FAIL is a measured 100% pass rate; SKIPPED is excluded.
    assert body["summary"]["pass_rate"] == 1.0
    assert body["trend"] == []


def test_scorecard_is_null_when_nothing_was_ever_scored(client, monkeypatch):
    _use(
        monkeypatch,
        quality_routes,
        _Conn(
            _regclass("quality_assertion"),
            _regclass("quality_result"),
            (
                "FROM   quality_assertion a",
                lambda s, p: [{"severity": "HIGH", "status": None}, {"severity": "HIGH", "status": "SKIPPED"}],
            ),
            ("to_char(date_trunc", lambda s, p: []),
            ("FROM   dataset d", lambda s, p: [{"count": 2}]),
        ),
    )
    response = client.get("/api/v1/quality/scorecard")
    assert response.status_code == 200
    assert response.json()["summary"]["pass_rate"] is None
