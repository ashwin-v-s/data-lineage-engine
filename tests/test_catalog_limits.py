"""Catalog paging and response truncation contract tests."""

from fastapi import Response

from backend.app.api.routes import search as search_module


class _Cursor:
    def __init__(self):
        self.query = ""
        self.params = ()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, query, params=()):
        self.query, self.params = " ".join(query.split()), params

    def fetchone(self):
        if "COUNT(*)" in self.query and "FROM dataset" in self.query:
            return {"count": 3}
        return {"count": 0}

    def fetchall(self):
        if "FROM dataset d" in self.query:
            return [
                {"id": "asset-1", "source_system": "dbt", "namespace": "prod",
                 "database_name": "warehouse", "schema_name": "sales", "name": "orders",
                 "asset_type": "table", "created_at": None, "column_count": 0},
                {"id": "asset-2", "source_system": "dbt", "namespace": "prod",
                 "database_name": "warehouse", "schema_name": "sales", "name": "returns",
                 "asset_type": "table", "created_at": None, "column_count": 0},
            ]
        if "FROM lineage_edge le" in self.query:
            return [{"id": f"edge-{n}"} for n in range(1001)]
        if "FROM evidence e" in self.query:
            return [{"id": f"evidence-{n}", "evidence_id": f"e-{n}",
                     "evidence_type": "STATIC_DEPENDENCY", "source_system": "dbt",
                     "run_id": None, "granularity": "DATASET", "operator": None,
                     "coverage": None, "diagnostics": None, "event_time": None,
                     "effective_time": None, "source_dataset": "warehouse.sales.orders",
                     "source_column": None, "target_dataset": "warehouse.sales.model",
                     "target_column": None, "state": "UNKNOWN"} for n in range(1001)]
        return []


class _Connection:
    def __init__(self):
        self.cur = _Cursor()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self, *_, **__):
        return self.cur


def test_catalog_page_and_graph_payloads_are_bounded(monkeypatch):
    monkeypatch.setattr(search_module, "get_conn", _Connection)
    response = Response()

    result = search_module.catalog_snapshot(response, limit=2, offset=0, user={"id": "user"})

    assert result["pagination"] == {"limit": 2, "offset": 0, "total_assets": 3}
    assert len(result["assets"]) == 2
    assert len(result["edges"]) == 1000
    assert len(result["evidence"]) == 1000
    assert result["truncated"] == {
        "assets": True, "edges": True, "evidence": True,
        "limits": {"assets_per_page": 2, "edges": 1000, "evidence": 1000},
    }
    assert response.headers["X-Total-Count"] == "3"
    assert response.headers["X-Result-Truncated"] == "true"
