"""Scheduled freshness runner and secret-protected trigger coverage."""
from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.app.api.routes import internal
from backend.app.main import app
from backend.app.services import freshness_runner

WORKSPACE_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
WORKSPACE_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
DATASET_A = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
DATASET_B = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
SECRET = "scheduled-test-secret"


def test_scheduled_trigger_fails_closed_without_a_configured_secret(monkeypatch):
    monkeypatch.delenv("KAIROS_CRON_SECRET", raising=False)

    response = TestClient(app).post("/api/v1/internal/freshness/run")

    assert response.status_code == 503


def test_scheduled_trigger_rejects_a_wrong_secret(monkeypatch):
    monkeypatch.setenv("KAIROS_CRON_SECRET", SECRET)

    response = TestClient(app).post(
        "/api/v1/internal/freshness/run",
        headers={"X-Kairos-Cron-Secret": "wrong"},
    )

    assert response.status_code == 401


def test_scheduled_trigger_runs_with_the_configured_secret(monkeypatch):
    monkeypatch.setenv("KAIROS_CRON_SECRET", SECRET)
    monkeypatch.setattr(
        internal,
        "run_scheduled_freshness",
        lambda: {"evaluated": 2, "failed": 0},
    )

    response = TestClient(app).post(
        "/api/v1/internal/freshness/run",
        headers={"X-Kairos-Cron-Secret": SECRET},
    )

    assert response.status_code == 200
    assert response.json() == {"evaluated": 2, "failed": 0}


def _target(workspace_id: str, dataset_id: str) -> dict:
    return {"workspace_id": workspace_id, "dataset_id": dataset_id}


def test_runner_scopes_each_target_to_its_own_workspace(monkeypatch):
    events = []
    current = {"workspace": None}

    class _Cursor:
        def __enter__(self):
            return object()

        def __exit__(self, *_exc):
            return False

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def cursor(self, **_kwargs):
            return _Cursor()

    @contextmanager
    def get_conn():
        events.append(("connect", current["workspace"]))
        yield _Connection()

    def set_workspace(workspace_id):
        current["workspace"] = workspace_id
        events.append(("set", workspace_id))
        return workspace_id

    def reset_workspace(token):
        events.append(("reset", token))
        current["workspace"] = None

    def evaluate(_conn, dataset_id, *, actor_user_id, mode):
        events.append(("evaluate", dataset_id, actor_user_id, mode))
        return SimpleNamespace(
            verdict=SimpleNamespace(state="UNKNOWN"),
            incident_action="none",
            incident_id=None,
            notification=None,
        )

    monkeypatch.setattr(
        freshness_runner,
        "list_freshness_targets",
        lambda: [_target(WORKSPACE_A, DATASET_A), _target(WORKSPACE_B, DATASET_B)],
    )
    monkeypatch.setattr(freshness_runner, "get_conn", get_conn)
    monkeypatch.setattr(freshness_runner, "set_workspace_id", set_workspace)
    monkeypatch.setattr(freshness_runner, "reset_workspace_id", reset_workspace)
    monkeypatch.setattr(freshness_runner, "evaluate_dataset_freshness", evaluate)

    result = freshness_runner.run_scheduled_freshness()

    assert result == {"evaluated": 2, "failed": 0}
    assert events == [
        ("set", WORKSPACE_A),
        ("connect", WORKSPACE_A),
        ("evaluate", DATASET_A, None, "SCHEDULED"),
        ("reset", WORKSPACE_A),
        ("set", WORKSPACE_B),
        ("connect", WORKSPACE_B),
        ("evaluate", DATASET_B, None, "SCHEDULED"),
        ("reset", WORKSPACE_B),
    ]


def test_runner_keeps_going_after_one_target_fails(monkeypatch):
    current = {"workspace": None}
    evaluated = []

    class _Cursor:
        def __enter__(self):
            return object()

        def __exit__(self, *_exc):
            return False

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def cursor(self, **_kwargs):
            return _Cursor()

    @contextmanager
    def get_conn():
        yield _Connection()

    def evaluate(_conn, dataset_id, *, actor_user_id, mode):
        if dataset_id == DATASET_A:
            raise RuntimeError("dataset evaluation failed")
        evaluated.append(dataset_id)
        return SimpleNamespace(
            verdict=SimpleNamespace(state="HEALTHY"),
            incident_action="none",
            incident_id=None,
            notification=None,
        )

    monkeypatch.setattr(
        freshness_runner,
        "list_freshness_targets",
        lambda: [_target(WORKSPACE_A, DATASET_A), _target(WORKSPACE_B, DATASET_B)],
    )
    monkeypatch.setattr(freshness_runner, "get_conn", get_conn)
    monkeypatch.setattr(
        freshness_runner,
        "set_workspace_id",
        lambda workspace_id: current.update(workspace=workspace_id) or workspace_id,
    )
    monkeypatch.setattr(
        freshness_runner,
        "reset_workspace_id",
        lambda _token: current.update(workspace=None),
    )
    monkeypatch.setattr(freshness_runner, "evaluate_dataset_freshness", evaluate)

    result = freshness_runner.run_scheduled_freshness()

    assert result == {"evaluated": 1, "failed": 1}
    assert evaluated == [DATASET_B]
    assert current["workspace"] is None
