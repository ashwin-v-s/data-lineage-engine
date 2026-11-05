"""Offline tests for the live PostgreSQL source connector.

The connector is pure and database-injectable: every test injects a fake
connector, so nothing here opens a socket or touches a database.
"""
from __future__ import annotations

import json

from ingestion.metadata_graph import CONTRACT_VERSION
from ingestion.postgres_source import (
    PostgresSourceConfig,
    extract_postgres_source,
)

_SECRET = "hunter2-password"


def _config() -> PostgresSourceConfig:
    return PostgresSourceConfig(
        host="db.internal",
        port=5433,
        dbname="analytics",
        user="bob",
        password=_SECRET,
        schema="public",
    )


def _two_table_connector(config):
    tables = [
        {"table_schema": "public", "table_name": "customers"},
        {"table_schema": "public", "table_name": "orders"},
    ]
    columns = [
        {
            "table_schema": "public",
            "table_name": "customers",
            "column_name": "id",
            "data_type": "integer",
            "is_nullable": "NO",
            "ordinal_position": 1,
        },
        {
            "table_schema": "public",
            "table_name": "customers",
            "column_name": "email",
            "data_type": "text",
            "is_nullable": "YES",
            "ordinal_position": 2,
        },
        {
            "table_schema": "public",
            "table_name": "orders",
            "column_name": "order_id",
            "data_type": "bigint",
            "is_nullable": "NO",
            "ordinal_position": 1,
        },
    ]
    return tables, columns


def test_extracts_two_tables_with_columns_and_no_relationships():
    result = extract_postgres_source(_config(), connector=_two_table_connector)
    assert result.ok is True
    payload = result.payload
    assert payload is not None
    assert payload["contract_version"] == CONTRACT_VERSION
    assert len(payload["assets"]) == 2
    assert [a["qualified_name"] for a in payload["assets"]] == [
        "public/customers",
        "public/orders",
    ]
    customers = next(a for a in payload["assets"] if a["name"] == "customers")
    assert customers["namespace"] == "public"
    assert customers["type"] == "TABLE"
    assert [c["name"] for c in customers["metadata"]["columns"]] == ["id", "email"]
    assert payload["relationships"] == []
    assert any(w.code == "NO_RELATIONSHIPS" for w in result.warnings)


def test_password_never_appears_in_the_payload():
    result = extract_postgres_source(_config(), connector=_two_table_connector)
    assert result.ok is True
    serialized = json.dumps(result.payload)
    assert _SECRET not in serialized
    assert "password" not in serialized.lower()


def test_empty_source_is_not_an_empty_success():
    def empty_connector(config):
        return [], []

    result = extract_postgres_source(_config(), connector=empty_connector)
    assert result.ok is False
    assert result.payload is None
    assert len(result.diagnostics) >= 1


def test_unreachable_source_reports_without_leaking_credentials():
    def boom_connector(config):
        raise RuntimeError("connection refused for user bob password hunter2")

    result = extract_postgres_source(_config(), connector=boom_connector)
    assert result.ok is False
    assert [d.code for d in result.diagnostics] == ["SOURCE_UNREACHABLE"]
    serialized = json.dumps(
        {
            "payload": result.payload,
            "diagnostics": [d.as_dict() for d in result.diagnostics],
            "warnings": [w.as_dict() for w in result.warnings],
        }
    )
    assert "hunter2" not in serialized
    assert "bob" not in serialized


def test_redacted_ref_excludes_the_password():
    ref = _config().redacted_ref
    assert ref == "db.internal:5433/analytics"
    assert "db.internal" in ref
    assert "5433" in ref
    assert "analytics" in ref
    assert _SECRET not in ref
