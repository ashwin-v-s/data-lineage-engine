"""
M1 Tests: Fingerprint Determinism

Tests that fingerprinting is deterministic: same SQL with different whitespace
produces identical fingerprints (query_fingerprint field).
"""

import pytest

from contracts.interfaces import SchemaSnapshot
from contracts.types import ParserStatus
from ingestion.sql import SQLGlotLineageProvider


class TestFingerprintDeterminism:
    """Test that fingerprints are consistent across whitespace variations."""

    def test_fingerprint_identical_with_extra_whitespace(self):
        """Same SQL with extra whitespace should produce identical fingerprint."""
        sql1 = "SELECT salary FROM employees WHERE country = 'US'"
        sql2 = "SELECT   salary   FROM   employees   WHERE   country   =   'US'"
        sql3 = """
        SELECT
            salary
        FROM
            employees
        WHERE
            country = 'US'
        """

        schema = SchemaSnapshot(
            dataset_id="employees",
            columns=("id", "name", "salary", "country"),
            fingerprint="schema-test",
        )

        provider = SQLGlotLineageProvider()
        result1 = provider.extract(sql1, schema)
        result2 = provider.extract(sql2, schema)
        result3 = provider.extract(sql3, schema)

        # All should succeed
        assert result1.parser_status == ParserStatus.SUPPORTED
        assert result2.parser_status == ParserStatus.SUPPORTED
        assert result3.parser_status == ParserStatus.SUPPORTED

        # All should have the same fingerprint
        fp1 = result1.evidence[0].query_fingerprint if result1.evidence else None
        fp2 = result2.evidence[0].query_fingerprint if result2.evidence else None
        fp3 = result3.evidence[0].query_fingerprint if result3.evidence else None

        assert fp1 is not None, "No evidence generated for sql1"
        assert fp2 is not None, "No evidence generated for sql2"
        assert fp3 is not None, "No evidence generated for sql3"
        assert fp1 == fp2, f"Fingerprints differ with extra whitespace: {fp1} vs {fp2}"
        assert fp1 == fp3, f"Fingerprints differ with multiline formatting: {fp1} vs {fp3}"

    def test_fingerprint_different_for_different_queries(self):
        """Different queries should produce different fingerprints."""
        sql1 = "SELECT salary FROM employees"
        sql2 = "SELECT name FROM employees"

        schema = SchemaSnapshot(
            dataset_id="employees",
            columns=("id", "name", "salary"),
            fingerprint="schema-test",
        )

        provider = SQLGlotLineageProvider()
        result1 = provider.extract(sql1, schema)
        result2 = provider.extract(sql2, schema)

        assert result1.parser_status == ParserStatus.SUPPORTED
        assert result2.parser_status == ParserStatus.SUPPORTED

        fp1 = result1.evidence[0].query_fingerprint if result1.evidence else None
        fp2 = result2.evidence[0].query_fingerprint if result2.evidence else None

        assert fp1 is not None
        assert fp2 is not None
        assert fp1 != fp2, "Different queries should have different fingerprints"

    def test_fingerprint_field_present_and_consistent(self):
        """Every StaticEvidence should have a consistent query_fingerprint."""
        sql = "SELECT col1, col2 FROM table1"
        schema = SchemaSnapshot(
            dataset_id="table1",
            columns=("col1", "col2"),
            fingerprint="schema-test",
        )

        provider = SQLGlotLineageProvider()
        result = provider.extract(sql, schema)

        assert result.parser_status == ParserStatus.SUPPORTED
        assert len(result.evidence) > 0

        # All evidence records should have the same query_fingerprint
        fingerprints = [ev.query_fingerprint for ev in result.evidence]
        assert len(set(fingerprints)) == 1, "All evidence from one query should share the same query_fingerprint"

    def test_fingerprint_length(self):
        """Fingerprints should be consistently short (SHA-256[:16])."""
        sql = "SELECT * FROM employees"
        schema = SchemaSnapshot(
            dataset_id="employees",
            columns=("id", "name", "salary"),
            fingerprint="schema-test",
        )

        provider = SQLGlotLineageProvider()
        result = provider.extract(sql, schema)

        if result.evidence:
            fp = result.evidence[0].query_fingerprint
            assert len(fp) == 16, f"Fingerprint should be 16 chars (SHA-256[:16]), got {len(fp)}"
