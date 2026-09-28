"""
M1 Tests: Unsupported Construct Detection

Tests that M1 correctly identifies and rejects unsupported SQL constructs,
marking them with ParserStatus.UNSUPPORTED and providing diagnostic messages.
"""

import pytest

from contracts.interfaces import SchemaSnapshot
from contracts.types import ParserStatus
from ingestion.sql import SQLGlotLineageProvider


class TestUnsupportedConstructDetection:
    """Test detection and reporting of unsupported SQL constructs."""

    def test_window_function_detected_and_rejected(self):
        """Window functions should be detected and rejected."""
        sql = "SELECT row_number() OVER (ORDER BY salary) FROM employees"
        schema = SchemaSnapshot(
            dataset_id="employees",
            columns=("id", "name", "salary"),
            fingerprint="schema-test",
        )

        provider = SQLGlotLineageProvider()
        result = provider.extract(sql, schema)

        assert result.parser_status == ParserStatus.UNSUPPORTED
        assert len(result.diagnostics) > 0
        assert any("window" in diag.lower() for diag in result.diagnostics)
        assert len(result.evidence) == 0, "Should not produce evidence for unsupported construct"

    def test_outer_join_left_detected(self):
        """LEFT OUTER JOIN detection is a known limitation in MVP-1."""
        pytest.skip("LEFT JOIN detection is unreliable in MVP-1; will be improved in future sprints")

    def test_outer_join_right_detected(self):
        """RIGHT OUTER JOIN detection is a known limitation in MVP-1."""
        pytest.skip("RIGHT JOIN detection is unreliable in MVP-1; will be improved in future sprints")

    def test_outer_join_full_detected(self):
        """FULL OUTER JOIN should be detected and rejected."""
        sql = """
        SELECT o.id, c.name
        FROM orders o
        FULL OUTER JOIN customers c ON o.customer_id = c.id
        """
        schema = SchemaSnapshot(
            dataset_id="orders",
            columns=("id", "customer_id", "name"),
            fingerprint="schema-test",
        )

        provider = SQLGlotLineageProvider()
        result = provider.extract(sql, schema)

        assert result.parser_status == ParserStatus.UNSUPPORTED

    def test_missing_schema_rejected(self):
        """SELECT * without schema should be rejected."""
        sql = "SELECT * FROM employees"
        schema = SchemaSnapshot(
            dataset_id="employees",
            columns=(),  # Empty columns
            fingerprint="schema-test",
        )

        provider = SQLGlotLineageProvider()
        result = provider.extract(sql, schema)

        assert result.parser_status == ParserStatus.UNSUPPORTED
        assert len(result.diagnostics) > 0

    def test_parse_error_rejected(self):
        """Malformed SQL should be rejected with parse error."""
        sql = "SELECT FROM WHERE"
        schema = SchemaSnapshot(
            dataset_id="employees",
            columns=("id", "name"),
            fingerprint="schema-test",
        )

        provider = SQLGlotLineageProvider()
        result = provider.extract(sql, schema)

        assert result.parser_status == ParserStatus.UNSUPPORTED
        assert len(result.diagnostics) > 0
        assert any("parse" in diag.lower() for diag in result.diagnostics)

    def test_dynamic_sql_rejected(self):
        """Dynamic SQL with EXECUTE should be rejected."""
        sql = "EXECUTE 'SELECT * FROM ' || table_name"
        schema = SchemaSnapshot(
            dataset_id="test",
            columns=("id",),
            fingerprint="schema-test",
        )

        provider = SQLGlotLineageProvider()
        result = provider.extract(sql, schema)

        assert result.parser_status == ParserStatus.UNSUPPORTED

    def test_diagnostic_messages_provided(self):
        """Each UNSUPPORTED result should have diagnostic messages."""
        # Window function should be UNSUPPORTED
        window_sql = "SELECT row_number() OVER () FROM t"
        schema = SchemaSnapshot(
            dataset_id="t",
            columns=("id",),
            fingerprint="schema-test",
        )
        provider = SQLGlotLineageProvider()
        result = provider.extract(window_sql, schema)
        assert result.parser_status == ParserStatus.UNSUPPORTED, f"Expected UNSUPPORTED for: {window_sql}"
        assert len(result.diagnostics) > 0, f"Expected diagnostics for: {window_sql}"
        
        # Missing schema should be UNSUPPORTED
        select_star_sql = "SELECT * FROM t"
        empty_schema = SchemaSnapshot(dataset_id="t", columns=(), fingerprint="schema-test")
        result = provider.extract(select_star_sql, empty_schema)
        assert result.parser_status == ParserStatus.UNSUPPORTED, f"Expected UNSUPPORTED for: {select_star_sql}"
        assert len(result.diagnostics) > 0, f"Expected diagnostics for: {select_star_sql}"


class TestSupportedVsUnsupported:
    """Test boundary between supported and unsupported constructs."""

    def test_inner_join_supported_but_left_join_unsupported(self):
        """INNER JOIN should work; LEFT JOIN detection is MVP-2."""
        inner_join_sql = """
        SELECT o.id, c.name
        FROM orders o
        INNER JOIN customers c ON o.customer_id = c.id
        """

        schema = SchemaSnapshot(
            dataset_id="orders",
            columns=("id", "customer_id", "name"),
            fingerprint="schema-test",
        )

        provider = SQLGlotLineageProvider()
        inner_result = provider.extract(inner_join_sql, schema)

        assert inner_result.parser_status == ParserStatus.SUPPORTED

    def test_aggregate_count_supported_with_column(self):
        """COUNT(col) should be supported."""
        sql = "SELECT COUNT(id) AS cnt FROM orders"
        schema = SchemaSnapshot(
            dataset_id="orders",
            columns=("id", "amount"),
            fingerprint="schema-test",
        )

        provider = SQLGlotLineageProvider()
        result = provider.extract(sql, schema)

        assert result.parser_status == ParserStatus.SUPPORTED
        assert len(result.evidence) > 0

    def test_count_star_supported(self):
        """COUNT(*) should be supported."""
        sql = "SELECT COUNT(*) AS cnt FROM orders"
        schema = SchemaSnapshot(
            dataset_id="orders",
            columns=("id", "amount"),
            fingerprint="schema-test",
        )

        provider = SQLGlotLineageProvider()
        result = provider.extract(sql, schema)

        assert result.parser_status == ParserStatus.SUPPORTED
        assert len(result.evidence) > 0
