from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.api.routes import workspaces
from backend.app.auth import require_user
from backend.app.main import app

USER = {"id": "11111111-1111-4111-8111-111111111111", "email": "owner@example.test", "user_metadata": {"full_name": "Kairos Owner"}}


class _Cursor:
    def __init__(self, mode): self.mode, self.result, self.sql, self.sqls = mode, None, "", []
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, sql, params=None):
        self.sql = sql
        self.sqls.append(sql)
        if "INSERT INTO kairos_welcome_email_delivery" in sql:
            self.result = None if self.mode in {"duplicate", "failed_retry"} else ("delivery-id",)
        elif "SET delivery_status='PENDING'" in sql:
            self.result = ("delivery-id",) if self.mode == "failed_retry" else None
        elif "SELECT delivery_status" in sql:
            self.result = ("FAILED" if self.mode == "failed_retry" else "SENT",)
        else:
            self.result = None
    def fetchone(self): return self.result


class _Conn:
    def __init__(self, mode): self.cur = _Cursor(mode)
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def cursor(self): return self.cur


def _client():
    app.dependency_overrides[require_user] = lambda: USER
    return TestClient(app)


def test_welcome_email_reports_missing_smtp_without_claiming_delivery(monkeypatch):
    monkeypatch.setattr(workspaces.EmailSettings, "from_env", classmethod(lambda cls: None))
    client = _client()
    try:
        response = client.post("/api/v1/me/welcome-email", json={"event_id": "22222222-2222-4222-8222-222222222222"})
    finally:
        app.dependency_overrides.pop(require_user, None)
    assert response.status_code == 503
    assert response.json()["error"]["message"] == "Welcome email is not configured on this server."


def test_welcome_email_sends_once_and_stores_delivery_status(monkeypatch):
    conn = _Conn("new")
    monkeypatch.setattr(workspaces.EmailSettings, "from_env", classmethod(lambda cls: object()))
    monkeypatch.setattr(workspaces, "get_conn", lambda: conn)
    sent = []
    monkeypatch.setattr(workspaces, "send_welcome_email", lambda email, name: sent.append((email, name)))
    client = _client()
    try:
        response = client.post("/api/v1/me/welcome-email", json={"event_id": "22222222-2222-4222-8222-222222222222"})
    finally:
        app.dependency_overrides.pop(require_user, None)
    assert response.status_code == 200
    assert response.json() == {"ok": True, "sent": True, "duplicate": False}
    assert sent == [("owner@example.test", "Kairos Owner")]
    assert conn.cur.sql.startswith("UPDATE kairos_welcome_email_delivery")


def test_duplicate_welcome_session_does_not_send_twice(monkeypatch):
    conn = _Conn("duplicate")
    monkeypatch.setattr(workspaces.EmailSettings, "from_env", classmethod(lambda cls: object()))
    monkeypatch.setattr(workspaces, "get_conn", lambda: conn)
    sent = []
    monkeypatch.setattr(workspaces, "send_welcome_email", lambda *args: sent.append(args))
    client = _client()
    try:
        response = client.post("/api/v1/me/welcome-email", json={"event_id": "22222222-2222-4222-8222-222222222222"})
    finally:
        app.dependency_overrides.pop(require_user, None)
    assert response.status_code == 200
    assert response.json() == {"ok": True, "sent": True, "duplicate": True, "delivery_status": "SENT"}
    assert sent == []


def test_failed_welcome_session_retries_same_event(monkeypatch):
    conn = _Conn("failed_retry")
    monkeypatch.setattr(workspaces.EmailSettings, "from_env", classmethod(lambda cls: object()))
    monkeypatch.setattr(workspaces, "get_conn", lambda: conn)
    sent = []
    monkeypatch.setattr(workspaces, "send_welcome_email", lambda email, name: sent.append((email, name)))
    client = _client()
    try:
        response = client.post("/api/v1/me/welcome-email", json={"event_id": "22222222-2222-4222-8222-222222222222"})
    finally:
        app.dependency_overrides.pop(require_user, None)
    assert response.status_code == 200
    assert response.json() == {"ok": True, "sent": True, "duplicate": False}
    assert sent == [("owner@example.test", "Kairos Owner")]
    assert any("SET delivery_status='PENDING'" in sql for sql in conn.cur.sqls)
