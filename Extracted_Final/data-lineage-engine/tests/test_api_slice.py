"""Optional: runs only if FastAPI is installed (M5 adds it to the dev dependencies)."""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import app  # noqa: E402

client = TestClient(app)


def test_health():
    assert client.get("/api/v1/health").json() == {"status": "ok"}


def test_dependency_states_come_from_the_real_engine_on_mock_data():
    ok = client.get("/api/v1/runs/run_B/dependency/employees.salary/out.adjusted_salary").json()
    assert ok["state"] == "REFUTED_FOR_RUN" and ok["is_mock"] is True
    lost = client.get("/api/v1/runs/run_C/dependency/employees.salary/out.adjusted_salary").json()
    assert lost["state"] == "POSSIBLE" and lost["warnings"] == ["NO_RUNTIME_EVENT_IS_NOT_NEGATIVE_EVIDENCE"]


def test_unknown_dependency_uses_the_stable_error_shape():
    r = client.get("/api/v1/runs/nope/dependency/a/b")
    assert r.status_code == 404
    err = r.json()["error"]
    assert err["code"] == "ENTITY_NOT_FOUND" and set(err) == {"code", "message", "details", "request_id"}
