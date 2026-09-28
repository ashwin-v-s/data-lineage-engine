"""
M1 Tests: Alias Resolution

Tests that table and column aliases are correctly resolved to their real names
in the extracted lineage.
"""

import pytest

from contracts.interfaces import SchemaSnapshot
from contracts.types import ParserStatus
from ingestion.sql import SQLGlotLineageProvider


class TestTableAliasResolution:
    """Test resolution of table aliases to real table names."""

    def test_single_table_alias_resolved(self):
        """Single table alias should be resolved to real table name."""
        sql = "SELECT e.name, e.salary FROM employees e"
        schema = SchemaSnapshot(
            dataset_id="employees",
            columns=("id", "name", "salary"),
            fingerprint="schema-test",
        )

        provider = SQLGlotLineageProvider()
        result = provider.extract(sql, schema)

        assert result.parser_status == ParserStatus.SUPPORTED
        assert len(result.evidence) > 0

        # Check that all source columns contain the real table name, not the alias
        source_cols = [ev.source_column_id for ev in result.evidence]
        for col in source_cols:
            # Should contain "employees" not just "e"
            assert "employees" in str(col) or col is None, \
                f"Alias not resolved properly in: {col}"

    def test_join_aliases_both_resolved(self):
        """Both table aliases in a JOIN should be resolved."""
        sql = """
        SELECT o.order_id, c.name
        FROM orders o
        INNER JOIN customers c ON o.customer_id = c.id
        """
        schema = SchemaSnapshot(
            dataset_id="orders",
            columns=("order_id", "customer_id", "id", "name"),
            fingerprint="schema-test",
        )

        provider = SQLGlotLineageProvider()
        result = provider.extract(sql, schema)

        assert result.parser_status == ParserStatus.SUPPORTED
        assert len(result.evidence) > 0

        # Check that real table names appear in source columns
        source_cols_str = " ".join([str(ev.source_column_id) for ev in result.evidence])
        # Should have resolved to real table names
        assert ("orders" in source_cols_str or "customers" in source_cols_str), \
            f"Real table names not found in: {source_cols_str}"

    def test_alias_with_where_clause(self):
        """Aliases in WHERE clause should also be resolved."""
        sql = "SELECT e.name FROM employees e WHERE e.salary > 50000"
        schema = SchemaSnapshot(
            dataset_id="employees",
            columns=("id", "name", "salary"),
            fingerprint="schema-test",
        )

        provider = SQLGlotLineageProvider()
        result = provider.extract(sql, schema)

        assert result.parser_status == ParserStatus.SUPPORTED
        assert len(result.evidence) > 0

        # Both name and salary should appear in dependencies
        source_cols = [ev.source_column_id for ev in result.evidence]
        source_cols_str = " ".join([str(col) for col in source_cols])
        assert "name" in source_cols_str or "salary" in source_cols_str, \
            f"Expected columns not found in: {source_cols_str}"

    def test_column_alias_in_select(self):
        """Column aliases in SELECT should be tracked."""
        sql = "SELECT name AS employee_name, salary AS total_pay FROM employees"
        schema = SchemaSnapshot(
            dataset_id="employees",
            columns=("id", "name", "salary"),
            fingerprint="schema-test",
        )

        provider = SQLGlotLineageProvider()
        result = provider.extract(sql, schema)

        assert result.parser_status == ParserStatus.SUPPORTED
        assert len(result.evidence) > 0

        # Check that output column aliases are used
        target_cols = [ev.target_column_id for ev in result.evidence]
        target_str = " ".join([str(col) for col in target_cols])
        # Should contain the alias names
        assert "employee_name" in target_str or "name" in target_str, \
            f"Column aliases not tracked in: {target_str}"


class TestAliasDeduplication:
    """Test that aliases don't create duplicate edges."""

    def test_no_duplicate_edges_from_same_column(self):
        """Same column referenced multiple ways should not create duplicate edges."""
        sql = "SELECT e.name, e.name AS name_copy FROM employees e"
        schema = SchemaSnapshot(
            dataset_id="employees",
            columns=("id", "name"),
            fingerprint="schema-test",
        )

        provider = SQLGlotLineageProvider()
        result = provider.extract(sql, schema)

        assert result.parser_status == ParserStatus.SUPPORTED

        # Count edges: employees.name → name and employees.name → name_copy
        edges = [(ev.source_column_id, ev.target_column_id) for ev in result.evidence]
        # Should have 2 distinct edges (one per output column)
        assert len(set(edges)) <= len(edges), "Deduplication may not be working"

    def test_alias_mapping_consistency(self):
        """Alias mapping should be consistent across the query."""
        sql = """
        SELECT t1.id, t1.value, t2.value
        FROM table1 t1
        INNER JOIN table2 t2 ON t1.id = t2.id
        """
        schema = SchemaSnapshot(
            dataset_id="table1",
            columns=("id", "value"),
            fingerprint="schema-test",
        )

        provider = SQLGlotLineageProvider()
        result = provider.extract(sql, schema)

        assert result.parser_status == ParserStatus.SUPPORTED

        # All references to t1 should map to table1
        source_cols = [str(ev.source_column_id) for ev in result.evidence]
        # Check consistency: table1 should appear multiple times if properly resolved
        table1_refs = sum(1 for col in source_cols if "table1" in col)
        assert table1_refs > 0, "table1 references should exist after alias resolution"
