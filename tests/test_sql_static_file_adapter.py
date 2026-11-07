from ingestion.sql.static_file import parse_sql_file


def test_sql_file_extracts_only_declared_create_table_dependencies():
    result = parse_sql_file(
        "CREATE TABLE analytics.revenue AS "
        "SELECT o.id, p.amount FROM analytics.orders o "
        "JOIN analytics.payments p ON p.order_id = o.id",
        filename="models/revenue.sql",
    )

    assert result.ok
    payload = result.payload
    assert payload["provenance"]["adapter"] == "kairos.sqlglot_file"
    sql_file = next(asset for asset in payload["assets"] if asset["type"] == "file")
    assert "CREATE TABLE analytics.revenue" in sql_file["metadata"]["original_sql"]
    assert {asset["qualified_name"] for asset in payload["assets"]} == {
        "sql-file/revenue.sql", "analytics.revenue", "analytics.orders", "analytics.payments",
    }
    assert {(edge["source_id"], edge["target_id"]) for edge in payload["relationships"]} == {
        ("sql-table:analytics.orders", "sql-table:analytics.revenue"),
        ("sql-table:analytics.payments", "sql-table:analytics.revenue"),
    }


def test_sql_file_select_without_declared_target_does_not_invent_lineage_edges():
    result = parse_sql_file("SELECT id FROM analytics.orders", filename="query.sql")

    assert result.ok
    assert result.payload["relationships"] == []
    assert {asset["qualified_name"] for asset in result.payload["assets"]} == {
        "sql-file/query.sql",
    }


def test_sql_file_reports_parser_errors_as_diagnostics():
    result = parse_sql_file("SELECT FROM", filename="broken.sql")

    assert not result.ok
    assert result.diagnostics[0].code == "SQL_PARSE_ERROR"
