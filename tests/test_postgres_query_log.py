"""
Tests for the PostgreSQL query-log capture adapter (B3).

Contracts verified:
  Q1  CREATE TABLE AS SELECT with two source tables → 2 assets, 2 POSSIBLE edges.
  Q2  INSERT INTO … SELECT → target + source assets and edges.
  Q3  Plain SELECT with no declared target → skipped, produces no edges.
  Q4  Mixed batch (CREATE, INSERT, SELECT) → only DDL/DML edges emitted.
  Q5  Every relationship has evidence_class=POSSIBLE (never OBSERVED or RUNTIME_POSITIVE).
  Q6  never_proves sentence is present on every relationship.
  Q7  Empty records list → EMPTY_QUERY_LOG diagnostic.
  Q8  Batch > MAX_QUERY_RECORDS → QUERY_LOG_TOO_LARGE diagnostic.
  Q9  Non-object record is collected as an error.
  Q10 JSON bytes input works.
  Q11 JSON string input works.
  Q12 JSON object with 'queries' key works.
  Q13 Invalid JSON → INVALID_JSON diagnostic.
  Q14 Non-list root → INVALID_QUERY_LOG diagnostic.
  Q15 Duplicate edges (same source→target from two queries) are deduplicated.
  Q16 Provenance carries adapter name, version, content_sha256, never_proves,
      scope_requirement, evidence_class.
  Q17 Two calls with identical input produce the same content_sha256.
  Q18 Static file dispatch: parse_static_file('postgres_query_log', ...) works.
  Q19 Unsupported kind still lists postgres_query_log in the error message.
  Q20 record with 'sql' key (alternative to 'query') works.
  Q21 record with 'statement' key works.
  Q22 All assets have inferred_from=postgres_query_log in metadata.
"""
from __future__ import annotations

import json

import pytest

from ingestion.postgres_query_log import parse_postgres_query_log, NEVER_PROVES
from ingestion.static_files import parse_static_file


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CREATE_SQL = (
    "CREATE TABLE analytics.order_summary AS "
    "SELECT o.order_id, p.amount "
    "FROM raw.orders AS o "
    "JOIN raw.payments AS p ON p.order_id = o.order_id"
)

INSERT_SQL = (
    "INSERT INTO reporting.daily_totals (day, total) "
    "SELECT DATE(created_at), SUM(amount) FROM raw.orders"
)

SELECT_SQL = "SELECT order_id, amount FROM raw.orders WHERE amount > 100"


def _records(*sqls: str) -> list[dict]:
    return [{"query": sql} for sql in sqls]


# ---------------------------------------------------------------------------
# Q1–Q4: basic parsing
# ---------------------------------------------------------------------------

class TestBasicParsing:

    def test_q1_create_table_as_produces_edges(self):
        r = parse_postgres_query_log(_records(CREATE_SQL))
        assert r.ok is True
        assert len(r.payload["assets"]) >= 3   # target + 2 sources
        assert len(r.payload["relationships"]) == 2

    def test_q2_insert_into_select_produces_edge(self):
        r = parse_postgres_query_log(_records(INSERT_SQL))
        assert r.ok is True
        assert len(r.payload["relationships"]) >= 1
        assert any("orders" in rel["source_id"] for rel in r.payload["relationships"])

    def test_q3_plain_select_skipped_no_edges(self):
        r = parse_postgres_query_log(_records(SELECT_SQL))
        # Either ok with 0 relationships, or NO_LINEAGE_CANDIDATES
        if r.ok:
            assert r.payload["relationships"] == []
        else:
            assert r.diagnostics[0].code == "NO_LINEAGE_CANDIDATES"

    def test_q4_mixed_batch_only_ddl_dml_produce_edges(self):
        r = parse_postgres_query_log(_records(CREATE_SQL, INSERT_SQL, SELECT_SQL))
        assert r.ok is True
        # CREATE + INSERT produce edges; SELECT does not
        assert len(r.payload["relationships"]) >= 2
        # SELECT-only source not referenced as a target
        target_ids = {rel["target_id"] for rel in r.payload["relationships"]}
        assert not any("orders" in t and "summary" not in t for t in target_ids), (
            "Plain SELECT must not produce a target asset"
        )


# ---------------------------------------------------------------------------
# Q5–Q6: evidence classification
# ---------------------------------------------------------------------------

class TestEvidenceClassification:

    def test_q5_all_relationships_are_possible_not_observed(self):
        r = parse_postgres_query_log(_records(CREATE_SQL))
        for rel in r.payload["relationships"]:
            assert rel["evidence_class"] == "POSSIBLE", (
                f"Relationship must be POSSIBLE, got {rel['evidence_class']!r}"
            )
            assert rel["edge_type"] == "sql_static_candidate"
            # Explicit: never OBSERVED or runtime
            assert rel["evidence_class"] != "OBSERVED"
            assert rel["evidence_class"] != "RUNTIME_POSITIVE"

    def test_q6_never_proves_in_every_relationship(self):
        r = parse_postgres_query_log(_records(CREATE_SQL, INSERT_SQL))
        for rel in r.payload["relationships"]:
            assert "never_proves" in rel["provenance"].lower() or NEVER_PROVES[:20] in rel["provenance"], (
                "never_proves sentence must appear in relationship provenance"
            )


# ---------------------------------------------------------------------------
# Q7–Q9: error cases
# ---------------------------------------------------------------------------

class TestErrorCases:

    def test_q7_empty_records_returns_diagnostic(self):
        r = parse_postgres_query_log([])
        assert r.ok is False
        assert r.diagnostics[0].code == "EMPTY_QUERY_LOG"

    def test_q8_too_many_records_returns_diagnostic(self):
        big_batch = [{"query": CREATE_SQL}] * 501
        r = parse_postgres_query_log(big_batch)
        assert r.ok is False
        assert r.diagnostics[0].code == "QUERY_LOG_TOO_LARGE"

    def test_q9_non_object_record_produces_error(self):
        r = parse_postgres_query_log(["not a dict", {"query": CREATE_SQL}])
        # Should fail with error on the non-dict record
        assert not r.ok
        assert any(d.code == "INVALID_QUERY_RECORD" for d in r.diagnostics)


# ---------------------------------------------------------------------------
# Q10–Q14: input format flexibility
# ---------------------------------------------------------------------------

class TestInputFormats:

    def test_q10_bytes_input_works(self):
        data = json.dumps(_records(CREATE_SQL)).encode("utf-8")
        r = parse_postgres_query_log(data)
        assert r.ok is True

    def test_q11_string_input_works(self):
        data = json.dumps(_records(CREATE_SQL))
        r = parse_postgres_query_log(data)
        assert r.ok is True

    def test_q12_object_with_queries_key_works(self):
        data = {"queries": _records(CREATE_SQL)}
        r = parse_postgres_query_log(json.dumps(data))
        assert r.ok is True

    def test_q12_object_with_statements_key_works(self):
        data = {"statements": _records(CREATE_SQL)}
        r = parse_postgres_query_log(json.dumps(data))
        assert r.ok is True

    def test_q13_invalid_json_returns_diagnostic(self):
        r = parse_postgres_query_log(b"not valid json {{")
        assert r.ok is False
        assert r.diagnostics[0].code == "INVALID_JSON"

    def test_q14_non_list_root_returns_diagnostic(self):
        r = parse_postgres_query_log(json.dumps({"query": "SELECT 1"}))
        assert r.ok is False
        assert r.diagnostics[0].code == "INVALID_QUERY_LOG"


# ---------------------------------------------------------------------------
# Q15: deduplication
# ---------------------------------------------------------------------------

class TestDeduplication:

    def test_q15_duplicate_edges_are_deduplicated(self):
        """Same source→target from two separate queries = one edge."""
        r = parse_postgres_query_log(_records(CREATE_SQL, CREATE_SQL))
        assert r.ok is True
        # Two identical CREATE statements → still only 2 unique edges
        assert len(r.payload["relationships"]) == 2


# ---------------------------------------------------------------------------
# Q16–Q17: provenance
# ---------------------------------------------------------------------------

class TestProvenance:

    def test_q16_provenance_fields_present(self):
        r = parse_postgres_query_log(_records(CREATE_SQL), filename="q.json")
        prov = r.payload["provenance"]
        assert prov["adapter"] == "kairos.postgres_query_log"
        assert prov["adapter_version"] == "1.0.0"
        assert len(prov["content_sha256"]) == 64
        assert "never_proves" in prov
        assert "scope_requirement" in prov
        assert prov["evidence_class"] == "POSSIBLE"
        assert prov["original_filename"] == "q.json"

    def test_q17_identical_input_same_sha256(self):
        r1 = parse_postgres_query_log(_records(CREATE_SQL))
        r2 = parse_postgres_query_log(_records(CREATE_SQL))
        assert r1.payload["provenance"]["content_sha256"] == r2.payload["provenance"]["content_sha256"]


# ---------------------------------------------------------------------------
# Q18–Q19: static file dispatch
# ---------------------------------------------------------------------------

class TestStaticFileDispatch:

    def test_q18_parse_static_file_dispatches_correctly(self):
        r = parse_static_file("postgres_query_log", _records(CREATE_SQL), filename="q.json")
        assert r.ok is True
        assert r.payload["provenance"]["adapter"] == "kairos.postgres_query_log"

    def test_q19_unsupported_kind_mentions_postgres_query_log(self):
        r = parse_static_file("unknown_kind", {})
        assert r.ok is False
        assert "postgres_query_log" in r.diagnostics[0].message


# ---------------------------------------------------------------------------
# Q20–Q22: alternative record fields and asset metadata
# ---------------------------------------------------------------------------

class TestRecordFields:

    def test_q20_sql_key_alternative_to_query(self):
        r = parse_postgres_query_log([{"sql": CREATE_SQL}])
        assert r.ok is True
        assert len(r.payload["relationships"]) >= 1

    def test_q21_statement_key_alternative(self):
        r = parse_postgres_query_log([{"statement": INSERT_SQL}])
        assert r.ok is True
        assert len(r.payload["relationships"]) >= 1

    def test_q22_assets_have_inferred_from_metadata(self):
        r = parse_postgres_query_log(_records(CREATE_SQL))
        for asset in r.payload["assets"]:
            assert asset["metadata"]["inferred_from"] == "postgres_query_log"
            assert "never_proves" in asset["metadata"]
