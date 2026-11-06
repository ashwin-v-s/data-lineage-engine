"""Offline acceptance coverage for freshness-to-incident orchestration.

The SQL double models the 0009 partial unique index
``(workspace_id, dedupe_key) WHERE status <> 'RESOLVED'`` under a lock. These
tests exercise the route logic and concurrency protocol, but do not replace an
isolated PostgreSQL/RLS integration test.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from threading import Barrier, RLock, Thread, local
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from backend.app.api.routes import governance
from backend.app.api.routes.governance import IncidentResolution

WORKSPACE_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
WORKSPACE_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
DATASET_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
OWNER_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
ACTOR = {"id": "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"}


class _Store:
    def __init__(self):
        self.lock = RLock()
        self.ids = 0
        self.evaluations = []
        self.incidents = []
        self.events = []
        self.notifications = []

    def new_id(self):
        with self.lock:
            self.ids += 1
            return str(UUID(int=self.ids))


class _Cursor:
    def __init__(self, store: _Store, workspace: str):
        self.store, self.workspace = store, workspace
        self.one = None
        self.many = []

    def __enter__(self): return self
    def __exit__(self, *_exc): return False

    def execute(self, query, params=()):
        sql = " ".join(query.split())
        self.one, self.many = None, []
        if "to_regclass" in sql:
            self.one = {"relation": params[0] if params else "public.required_table"}
        elif sql.startswith("SELECT id::text AS id, name FROM dataset"):
            self.one = {"id": DATASET_ID, "name": "orders"}
        elif "SELECT id::text AS id, warn_after_minutes" in sql:
            self.one = {"id": "sla-1", "warn_after_minutes": 60, "error_after_minutes": 75,
                        "stale_after_minutes": 120, "signal": "openlineage_run", "paused": False}
        elif "JOIN execution_run er ON er.run_id = e.run_id" in sql:
            self.one = {"last_activity": datetime.now(timezone.utc) - timedelta(minutes=90),
                        "evidence_id": UUID("ffffffff-ffff-4fff-8fff-ffffffffffff"),
                        "run_id": "ol-run-1", "evidence_ref": {"kind": "SUCCESSFUL_RUNTIME_EVIDENCE", "run_id": "ol-run-1"}}
        elif sql.startswith("INSERT INTO freshness_evaluation"):
            row = {"id": self.store.new_id(), "workspace_id": self.workspace, "dataset_id": params[0],
                   "state": params[2], "evidence_id": params[7], "evidence_ref": params[8].adapted}
            with self.store.lock: self.store.evaluations.append(row)
            self.one = {"id": row["id"]}
        elif sql.startswith("SELECT owner_id FROM dataset"):
            self.one = {"owner_id": OWNER_ID}
        elif sql.startswith("SELECT user_id::text FROM workspace_member"):
            self.one = {"user_id": OWNER_ID} if params[0] == OWNER_ID else None
        elif sql.startswith("INSERT INTO incident "):
            dedupe_key = params[3]
            # Emulate the database's partial unique index as the atomic arbiter.
            with self.store.lock:
                existing = next((item for item in self.store.incidents
                                 if item["workspace_id"] == self.workspace and item["dedupe_key"] == dedupe_key
                                 and item["status"] != "RESOLVED"), None)
                if existing:
                    self.one = None
                else:
                    incident = {"id": self.store.new_id(), "workspace_id": self.workspace,
                                "dataset_id": params[0], "title": params[1], "severity": params[2],
                                "status": "DETECTED", "dedupe_key": dedupe_key,
                                "detail": params[4].adapted, "assigned_user_id": params[5]}
                    self.store.incidents.append(incident)
                    self.one = {"id": incident["id"]}
        elif sql.startswith("SELECT id::text AS id FROM incident WHERE dedupe_key"):
            row = next((item for item in self.store.incidents if item["workspace_id"] == self.workspace
                        and item["dedupe_key"] == params[0] and item["status"] != "RESOLVED"), None)
            self.one = {"id": row["id"]} if row else None
        elif sql.startswith("SELECT id::text AS id, status FROM incident WHERE id = %s::uuid FOR UPDATE"):
            row = next((x for x in self.store.incidents if x["id"] == params[0] and x["workspace_id"] == self.workspace), None)
            self.one = {"id": row["id"], "status": row["status"]} if row else None
        elif sql.startswith("INSERT INTO incident_event"):
            event_type = "DETECTED" if "'DETECTED'" in sql else params[1]
            actor = params[1] if event_type == "DETECTED" else params[2]
            detail = params[2] if event_type == "DETECTED" else params[3]
            with self.store.lock:
                self.store.events.append({"incident_id": str(params[0]), "workspace_id": self.workspace,
                                          "event_type": event_type, "actor_user_id": str(actor),
                                          "detail": detail.adapted, "created_at": datetime.now(timezone.utc)})
        elif sql.startswith("UPDATE incident SET status = %s, resolved_at"):
            with self.store.lock:
                row = next((x for x in self.store.incidents if x["id"] == params[2] and x["workspace_id"] == self.workspace), None)
                if row:
                    row["status"] = params[0]
                    row["resolution_detail"] = params[1].adapted
        elif sql.startswith("UPDATE incident SET status = %s"):
            with self.store.lock:
                row = next((x for x in self.store.incidents if x["id"] == params[1] and x["workspace_id"] == self.workspace), None)
                if row: row["status"] = params[0]
        elif "FROM incident i JOIN dataset d" in sql:
            row = next((x for x in self.store.incidents if x["id"] == params[0] and x["workspace_id"] == self.workspace), None)
            if row:
                self.one = {**row, "dataset_name": "orders", "opened_at": datetime.now(timezone.utc),
                            "acknowledged_at": None, "resolved_at": None,
                            "owner_user_id": row.get("assigned_user_id"), "resolution_detail": row.get("resolution_detail")}
        elif "FROM incident_event ev" in sql:
            self.many = [x for x in self.store.events if x["incident_id"] == params[0] and x["workspace_id"] == self.workspace]
        elif "SELECT id::text,title,severity,status,opened_at FROM incident" in sql:
            self.many = []
        elif sql.startswith("INSERT INTO notification "):
            with self.store.lock: self.store.notifications.append({"workspace_id": self.workspace, "recipient": params[0], "type": params[1], "detail": params[3].adapted})
        else:
            raise AssertionError(f"Unexpected SQL: {sql}")

    def fetchone(self): return self.one
    def fetchall(self): return self.many


class _Connection:
    def __init__(self, store, workspace): self.store, self.workspace = store, workspace
    def __enter__(self): return self
    def __exit__(self, *_exc): return False
    def cursor(self, **_kwargs): return _Cursor(self.store, self.workspace)


@pytest.fixture
def fake_governance_db(monkeypatch):
    store, scope = _Store(), local()

    @contextmanager
    def get_conn():
        yield _Connection(store, getattr(scope, "workspace", WORKSPACE_A))

    monkeypatch.setattr(governance, "get_conn", get_conn)
    return store, scope


def _evaluate(workspace=WORKSPACE_A):
    return governance.evaluate_dataset(UUID(DATASET_ID), dict(ACTOR))


def test_repeated_freshness_breach_has_one_active_incident_and_preserves_evidence(fake_governance_db):
    store, scope = fake_governance_db
    scope.workspace = WORKSPACE_A
    first = _evaluate()
    second = _evaluate()

    assert first["verdict"]["state"] == second["verdict"]["state"] == "LATE"
    assert first["incident_action"] == "created"
    assert second["incident_action"] == "existing"
    assert first["incident_id"] == second["incident_id"]
    assert len([i for i in store.incidents if i["workspace_id"] == WORKSPACE_A and i["status"] != "RESOLVED"]) == 1
    incident = store.incidents[0]
    assert incident["dataset_id"] == DATASET_ID
    assert incident["assigned_user_id"] == OWNER_ID
    assert incident["detail"]["evidence_id"] == "ffffffff-ffff-4fff-8fff-ffffffffffff"
    assert incident["detail"]["evaluation_id"] == store.evaluations[0]["id"]
    assert [event["event_type"] for event in store.events] == ["DETECTED"]
    assert len(store.notifications) == 1


def test_concurrent_evaluations_follow_the_partial_unique_index_design(fake_governance_db):
    store, scope = fake_governance_db
    scope.workspace = WORKSPACE_A
    barrier = Barrier(8)
    results, failures = [], []

    def run_one():
        try:
            barrier.wait(timeout=5)
            results.append(_evaluate())
        except Exception as exc:  # surfaced below with the original test failure
            failures.append(exc)

    threads = [Thread(target=run_one) for _ in range(8)]
    for thread in threads: thread.start()
    for thread in threads: thread.join(timeout=10)
    assert not any(thread.is_alive() for thread in threads)
    assert failures == []
    assert len(results) == 8
    assert len([i for i in store.incidents if i["workspace_id"] == WORKSPACE_A and i["status"] != "RESOLVED"]) == 1
    assert sum(1 for event in store.events if event["event_type"] == "DETECTED") == 1
    assert sum(1 for item in store.notifications if item["type"] == "FRESHNESS_BREACH") == 1


def test_foreign_workspace_incident_read_is_hidden_and_resolution_is_audited(fake_governance_db):
    store, scope = fake_governance_db
    scope.workspace = WORKSPACE_A
    result = _evaluate()
    incident_id = UUID(result["incident_id"])

    scope.workspace = WORKSPACE_B
    with pytest.raises(HTTPException) as missing:
        governance.get_incident(incident_id, dict(ACTOR))
    assert missing.value.status_code == 404

    scope.workspace = WORKSPACE_A
    resolved = governance.resolve_incident(
        incident_id,
        IncidentResolution(reason="Verified source completion", action_taken="Replayed successful run"),
        dict(ACTOR),
    )
    assert resolved["status"] == "RESOLVED"
    assert resolved["resolution_detail"] == {
        "reason": "Verified source completion",
        "action_taken": "Replayed successful run",
        "resolved_by": ACTOR["id"],
    }
    assert [event["event_type"] for event in resolved["events"]] == ["DETECTED", "RESOLVED"]
