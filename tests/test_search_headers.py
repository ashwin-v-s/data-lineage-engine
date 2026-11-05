"""Keyword-search pagination response headers."""

from fastapi import Response

from backend.app.api.routes import search as search_module


class _Cursor:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, query, params):
        self.query = query

    def fetchone(self):
        return {"total": 22}

    def fetchall(self):
        return [{
            "id": f"asset-{index}", "type": "TABLE", "name": f"warehouse.sales.orders_{index}",
            "label": f"orders_{index}", "schema": "sales", "owner": None,
            "description": None, "created": None, "updated": None,
            "row_count": None, "steward": None, "tags": None,
        } for index in range(10)]


class _Connection:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self, *_, **__):
        return _Cursor()


def test_search_returns_total_and_page_truncation_headers(monkeypatch):
    monkeypatch.setattr(search_module, "get_conn", _Connection)
    response = Response()

    result = search_module.search(
        response=response, q="orders", page=2, page_size=10,
        sort_by="name", sort_order="asc", asset_type=None,
    )

    assert result.total == 22
    assert len(result.results) == 10
    assert response.headers["X-Total-Count"] == "22"
    assert response.headers["X-Result-Truncated"] == "true"
