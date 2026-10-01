"""Contract and integration tests for Kairos API layer (Section 17, 24).

Verifies:
- M3 Entity lookup (by id, by fqn)
- M3 Lineage graph (whole-graph, upstream, downstream, bitemporal slicing, truncation headers)
- Invalid temporal parameters (400 INVALID_TEMPORAL_PARAMETER)
- M3 Evidence dossier (by id, by entity, search, raw_event payload_hash)
- M4 Reasoning integration (OBSERVED, REFUTED_FOR_RUN, POSSIBLE, UNKNOWN with verbatim Section 12 text)
- Error handling shapes
- Benchmark evaluation oracle isolation
"""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["db"] == "connected"


def test_entity_endpoints():
    # By ID
    res = client.get("/api/v1/entities/orders_fact")
    assert res.status_code == 200
    assert res.json()["data"]["name"] == "orders_fact"

    # By FQN
    res_fqn = client.get("/api/v1/entities/by-name?fqn=kairos_dw.hr.employees.salary")
    assert res_fqn.status_code == 200
    assert res_fqn.json()["data"]["column_name"] == "salary"

    # 404 Entity Not Found
    res_404 = client.get("/api/v1/entities/unknown_entity_id")
    assert res_404.status_code == 404
    err = res_404.json()
    assert err["success"] is False
    assert err["error"]["code"] == "ENTITY_NOT_FOUND"


def test_lineage_graph_and_truncation_headers():
    res = client.get("/api/v1/lineage/orders_fact/graph?depth=2")
    assert res.status_code == 200
    data = res.json()
    assert data["center_node"]["name"] == "orders_fact"
    assert len(data["nodes"]) >= 3
    assert len(data["edges"]) >= 3

    # Check Truncation headers per Section 16
    assert "x-result-truncated" in res.headers
    assert res.headers["x-result-truncated"] in ("true", "false")
    assert "x-total-count" in res.headers
    assert "x-returned-count" in res.headers


def test_lineage_upstream_downstream():
    up = client.get("/api/v1/lineage/orders_fact/upstream?depth=1").json()
    for e in up["edges"]:
        assert e["target"] in ("orders_fact", "e3b1c4a0-7f28-4c8d-965a-8d7b32c694a1")

    down = client.get("/api/v1/lineage/orders_fact/downstream?depth=1").json()
    for e in down["edges"]:
        assert e["source"] in ("orders_fact", "e3b1c4a0-7f28-4c8d-965a-8d7b32c694a1")


def test_bitemporal_temporal_filtering():
    # Live query -> stg_customer_orders is OBSERVED
    res_live = client.get("/api/v1/lineage/orders_fact/graph").json()
    stg_live = [e for e in res_live["edges"] if e["source"] == "stg_customer_orders"][0]
    assert stg_live["reasoning_state"] == "OBSERVED"

    # Historical slice before 2026-09-01 -> stg_customer_orders reverts to UNKNOWN
    res_hist = client.get("/api/v1/lineage/orders_fact/graph?valid_at=2026-08-15T00:00:00Z").json()
    stg_hist = [e for e in res_hist["edges"] if e["source"] == "stg_customer_orders"][0]
    assert stg_hist["reasoning_state"] == "UNKNOWN"


def test_invalid_temporal_parameter():
    res = client.get("/api/v1/lineage/orders_fact/graph?valid_at=not-a-date")
    assert res.status_code == 400
    err = res.json()
    assert err["success"] is False
    assert err["error"]["code"] == "INVALID_TEMPORAL_PARAMETER"
    assert err["error"]["parameter"] == "valid_at"


def test_evidence_endpoints():
    # Detail by ID
    res = client.get("/api/v1/evidence/ev_stg_orders_01")
    assert res.status_code == 200
    dossier = res.json()["data"]
    assert dossier["evidence_id"] == "ev_stg_orders_01"
    assert dossier["raw_event"]["payload_hash"].startswith("sha256:")
    assert dossier["parser_status"] == "SUPPORTED"

    # Search
    res_search = client.get("/api/v1/evidence/search?evidence_type=STATIC_AST")
    assert res_search.status_code == 200
    assert res_search.json()["total"] >= 1

    # Entity evidence
    res_ent = client.get("/api/v1/evidence/entity/orders_fact")
    assert res_ent.status_code == 200
    assert "data" in res_ent.json()


def test_m4_reasoning_and_fixed_interpretations():
    # Run B -> REFUTED_FOR_RUN
    b_res = client.get("/api/v1/runs/run_B/dependency/employees.salary/out.adjusted_salary").json()
    assert b_res["state"] == "REFUTED_FOR_RUN"
    assert b_res["interpretation"] == "No propagation was established for this run under complete-evaluation conditions."

    # Run C -> POSSIBLE
    c_res = client.get("/api/v1/runs/run_C/dependency/employees.salary/out.adjusted_salary").json()
    assert c_res["state"] == "POSSIBLE"
    assert c_res["interpretation"] == "Static analysis permits this dependency, but available evidence is insufficient to establish whether propagation occurred in this run."
    assert "NO_RUNTIME_EVENT_IS_NOT_NEGATIVE_EVIDENCE" in c_res["warnings"]

    # Run A -> OBSERVED
    a_res = client.get("/api/v1/runs/run_A/dependency/employees.salary/out.adjusted_salary").json()
    assert a_res["state"] == "OBSERVED"
    assert a_res["interpretation"] == "Positive runtime evidence establishes observed propagation for this run."


def test_evaluation_oracle_isolated_mode():
    res = client.get("/api/v1/evaluation/oracle/run_2026_09_23_093214")
    assert res.status_code == 200
    data = res.json()
    assert data["is_evaluation_mode"] is True
    assert "BENCHMARK EVALUATION ONLY" in data["warning"]
    assert len(data["records"]) > 0
