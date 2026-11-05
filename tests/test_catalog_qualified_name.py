"""Catalog qualified-name mapping for uploaded artifacts.

The ingestion commit used to store ``database_name='metadata'`` as a NOT NULL
placeholder, which made the catalog API return
``metadata.warehouse.raw.orders`` and put the placeholder into every graph node
path.  These tests pin the identity the lineage graph depends on, for rows
written before and after the fix, and for the legacy catalog.
"""

from backend.app.api.routes.ingestion import _split_namespace
from backend.app.api.routes.search import _qualified_name


def _asset(**overrides):
    row = {
        "namespace": "warehouse.raw",
        "database_name": "",
        "schema_name": "warehouse.raw",
        "name": "orders",
    }
    row.update(overrides)
    return row


def test_pre_fix_upload_row_drops_placeholder_database():
    assert _qualified_name(_asset(database_name="metadata")) == "warehouse.raw.orders"


def test_new_upload_row_keeps_the_namespace_path():
    assert _qualified_name(_asset()) == "warehouse.raw.orders"


def test_single_segment_namespace_has_no_empty_segment():
    asset = _asset(namespace="analytics", schema_name="analytics", name="orders_model")
    assert _qualified_name(asset) == "analytics.orders_model"


def test_legacy_catalog_rows_keep_database_schema_name():
    asset = _asset(
        namespace="warehouse",
        database_name="prod",
        schema_name="commerce",
        name="customer_orders",
    )
    assert _qualified_name(asset) == "prod.commerce.customer_orders"


def test_placeholder_database_without_namespace_is_preserved():
    asset = _asset(namespace="", database_name="metadata", schema_name="demo", name="table_a")
    assert _qualified_name(asset) == "metadata.demo.table_a"


def test_namespace_maps_onto_the_not_null_identity_tuple():
    assert _split_namespace("warehouse.raw") == ("", "warehouse.raw")
    assert _split_namespace("analytics") == ("", "analytics")
    assert _split_namespace("") == ("", "")
    assert _split_namespace("x" * 400)[1] == "x" * 200
