"""Database lookup behavior for non-reversible canonical dataset UUIDs."""

from backend.app.identity.canonical_ids import dataset_id, parse_dataset_components


class _Cursor:
    def __init__(self, row):
        self.row = row
        self.executed = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, query, params):
        self.executed = (query, params)

    def fetchone(self):
        return self.row


class _Connection:
    def __init__(self, row):
        self.cursor_instance = _Cursor(row)

    def cursor(self):
        return self.cursor_instance


def test_dataset_components_are_looked_up_from_stored_identity():
    conn = _Connection(("dbt", "prod", "warehouse", "sales", "orders", "table"))
    canonical = dataset_id("dbt", "prod", "warehouse", "sales", "orders", "table")

    assert parse_dataset_components(conn, str(canonical)) == (
        "dbt", "prod", "warehouse", "sales", "orders", "table"
    )
    query, params = conn.cursor_instance.executed
    assert "FROM dataset" in query
    assert "WHERE id = %s" in query
    assert params == (str(canonical),)


def test_dataset_lookup_returns_none_for_malformed_or_invisible_ids():
    conn = _Connection(None)
    assert parse_dataset_components(conn, "not-a-uuid") is None
    assert conn.cursor_instance.executed is None
    assert parse_dataset_components(conn, "11111111-1111-4111-8111-111111111111") is None
