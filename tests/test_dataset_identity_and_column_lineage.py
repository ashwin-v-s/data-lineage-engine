"""Canonical dataset identity and column-level static lineage.

BUG-01: adapters assigned their own asset type and stored the import artifact
name in the dataset's database slot, so one table became several catalog rows.
BUG-03: static SQL imports emitted only dataset edges, so ``/column-lineage``
always returned an empty list.
"""
from __future__ import annotations

from backend.app.identity.canonical_ids import (
    asset_identity_kind,
    canonical_asset_type,
    canonical_import_identity,
)
from ingestion.metadata_graph import parse_metadata_graph
from ingestion.sql.static_file import parse_sql_file

# ── BUG-01: canonical identity ───────────────────────────────────────────────

def test_asset_types_normalise_to_one_spelling():
    assert canonical_asset_type("table") == "TABLE"
    assert canonical_asset_type(" Seed ") == "TABLE"
    assert canonical_asset_type("snapshot") == "MODEL"
    assert canonical_asset_type("materialized-view") == "VIEW"
    assert canonical_asset_type("dashboard") == "DASHBOARD"
    assert canonical_asset_type(None) == "TABLE"


def test_data_asset_types_share_the_dataset_identity_group():
    groups = {
        asset_identity_kind(value)
        for value in ("source", "table", "view", "model", "TABLE", "MODEL")
    }
    assert groups == {"DATASET"}
    # A dashboard or file with the same name is a different kind of asset.
    assert asset_identity_kind("dashboard") == "DASHBOARD"
    assert asset_identity_kind("file") == "FILE"


def test_import_identity_uses_the_declared_schema_not_the_artifact_name():
    dbt_source = {
        "namespace": "dbt/enterprise_revenue_lakehouse/source",
        "name": "customers",
        "type": "source",
        "metadata": {"database": "enterprise_dw", "schema": "raw_enterprise"},
    }
    sql_table = {
        "namespace": "raw_enterprise",
        "name": "customers",
        "type": "table",
        "metadata": {},
    }
    assert canonical_import_identity(dbt_source) == ("", "raw_enterprise", "SOURCE")
    assert canonical_import_identity(sql_table) == ("", "raw_enterprise", "TABLE")


def test_import_identity_falls_back_to_the_last_namespace_segment():
    file_asset = {"namespace": "filesystem", "name": "orders.csv", "type": "file"}
    assert canonical_import_identity(file_asset) == ("", "filesystem", "FILE")


# ── BUG-03: static column lineage ────────────────────────────────────────────

def _pairs(payload: dict) -> set[tuple[str, str, str, str]]:
    return {
        (rel["source_id"], rel["source_column"], rel["target_id"], rel["target_column"])
        for rel in payload["relationships"]
        if rel.get("source_column")
    }


def test_create_table_as_select_emits_column_pairs():
    sql = """
    CREATE TABLE staging.orders_enriched AS
    SELECT o.order_id,
           o.amount + o.tax AS gross_value,
           COALESCE(p.settled, 0) AS settled_value
    FROM raw.orders o
    JOIN raw.payments p ON o.order_id = p.order_id
    """
    result = parse_sql_file(sql, filename="pipeline.sql")
    assert result.ok
    pairs = _pairs(result.payload)
    assert ("sql-table:raw.orders", "order_id", "sql-table:staging.orders_enriched", "order_id") in pairs
    assert ("sql-table:raw.orders", "amount", "sql-table:staging.orders_enriched", "gross_value") in pairs
    assert ("sql-table:raw.orders", "tax", "sql-table:staging.orders_enriched", "gross_value") in pairs
    assert ("sql-table:raw.payments", "settled", "sql-table:staging.orders_enriched", "settled_value") in pairs


def test_insert_column_list_maps_target_columns_by_position():
    sql = """
    INSERT INTO analytics.daily_revenue (revenue_date, revenue_total)
    SELECT CAST(s.created_at AS DATE), SUM(s.amount)
    FROM staging.sales s
    """
    result = parse_sql_file(sql, filename="mart.sql")
    assert result.ok
    pairs = _pairs(result.payload)
    assert ("sql-table:staging.sales", "created_at", "sql-table:analytics.daily_revenue", "revenue_date") in pairs
    assert ("sql-table:staging.sales", "amount", "sql-table:analytics.daily_revenue", "revenue_total") in pairs


def test_column_candidates_populate_asset_columns():
    sql = "CREATE TABLE staging.out AS SELECT o.id, o.amount AS total FROM raw.orders o"
    result = parse_sql_file(sql, filename="x.sql")
    columns = {
        asset["name"]: {column["name"] for column in asset["metadata"].get("columns", [])}
        for asset in result.payload["assets"]
    }
    assert columns["orders"] == {"id", "amount"}
    assert columns["out"] == {"id", "total"}


def test_select_star_does_not_invent_column_mappings():
    sql = "CREATE TABLE staging.copy AS SELECT * FROM raw.orders"
    result = parse_sql_file(sql, filename="copy.sql")
    assert result.ok
    assert _pairs(result.payload) == set()


def test_metadata_graph_accepts_many_column_pairs_between_two_assets():
    graph = {
        "contract_version": "kairos.ingest.v1",
        "assets": [
            {"id": "a", "qualified_name": "raw/orders", "namespace": "raw", "name": "orders", "type": "table"},
            {"id": "b", "qualified_name": "staging/orders", "namespace": "staging", "name": "orders", "type": "table"},
        ],
        "relationships": [
            {"source_id": "a", "target_id": "b", "edge_type": "projection", "source_column": "id", "target_column": "id"},
            {"source_id": "a", "target_id": "b", "edge_type": "projection", "source_column": "amount", "target_column": "total"},
        ],
    }
    result = parse_metadata_graph(graph)
    assert result.ok, [diagnostic.as_dict() for diagnostic in result.diagnostics]
    assert len(result.payload["relationships"]) == 2


def test_metadata_graph_rejects_half_a_column_pair():
    graph = {
        "contract_version": "kairos.ingest.v1",
        "assets": [
            {"id": "a", "qualified_name": "raw/orders", "namespace": "raw", "name": "orders", "type": "table"},
            {"id": "b", "qualified_name": "staging/orders", "namespace": "staging", "name": "orders", "type": "table"},
        ],
        "relationships": [
            {"source_id": "a", "target_id": "b", "edge_type": "projection", "source_column": "id"},
        ],
    }
    result = parse_metadata_graph(graph)
    assert not result.ok
    assert any(d.code == "INCOMPLETE_COLUMN_RELATIONSHIP" for d in result.diagnostics)
