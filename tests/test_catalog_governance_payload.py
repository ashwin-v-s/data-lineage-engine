"""The catalog snapshot must surface stored quality results and PII classifications.

Before this contract, `/api/v1/catalog` always returned empty arrays, so the Data
quality page and the PII overlay could never show records that existed in the
database. These tests pin the payload shape the dashboard consumes.
"""

from datetime import datetime, timezone

from fastapi import Response

from backend.app.api.routes import search as search_module


class _Cursor:
    def __init__(self):
        self.query = ""

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, query, params=()):
        self.query = " ".join(query.split())

    def fetchone(self):
        if "to_regclass" in self.query:
            return {"assertions": "quality_assertion", "classifications": "pii_classification"}
        if "COUNT(*)" in self.query and "FROM dataset" in self.query:
            return {"count": 1}
        return {"count": 0}

    def fetchall(self):
        if "FROM dataset d" in self.query:
            return [{
                "id": "11111111-1111-4111-8111-111111111111", "source_system": "upload",
                "namespace": "analytics", "database_name": "", "schema_name": "analytics",
                "name": "fct_daily_revenue", "asset_type": "TABLE", "created_at": None,
                "column_count": 6,
            }]
        if "FROM quality_assertion qa" in self.query:
            return [{
                "id": "22222222-2222-4222-8222-222222222222",
                "rule_name": "Revenue mart schema contract",
                "check_type": "schema",
                "severity": "HIGH",
                "dataset_id": "11111111-1111-4111-8111-111111111111",
                "qualified_asset_name": "fct_daily_revenue",
                "status": "PASS",
                "checked_count": 6,
                "failed_count": 0,
                "evaluated_at": datetime(2026, 11, 21, 11, 36, tzinfo=timezone.utc),
            }]
        if "FROM pii_classification pc" in self.query:
            return [{
                "id": "33333333-3333-4333-8333-333333333333",
                "asset_id": "11111111-1111-4111-8111-111111111111",
                "asset_name": "customers",
                "column_id": "44444444-4444-4444-8444-444444444444",
                "column_name": "email",
                "classification": "PII_SOURCE",
                "evidence_state": "OBSERVED",
                "provenance": {"origin": "manual_steward", "note": "ERP customer master"},
                "created_at": datetime(2026, 11, 21, 11, 30, tzinfo=timezone.utc),
            }]
        return []


class _Connection:
    def __init__(self):
        self.cur = _Cursor()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self, *_, **__):
        return self.cur


def test_catalog_returns_stored_quality_results_and_classifications(monkeypatch):
    monkeypatch.setattr(search_module, "get_conn", _Connection)

    result = search_module.catalog_snapshot(Response(), limit=100, offset=0, user={"id": "user"})

    assert len(result["quality_checks"]) == 1
    check = result["quality_checks"][0]
    assert check["rule_name"] == "Revenue mart schema contract"
    assert check["check_type"] == "schema"
    assert check["qualified_asset_name"] == "fct_daily_revenue"
    assert check["status"] == "PASS"
    assert check["checked_count"] == 6
    # Metadata assertions are not scored; the dashboard must see null, not 0.
    assert check["score"] is None
    assert check["evaluated_at"] == "2026-11-21T11:36:00+00:00"

    assert len(result["column_classifications"]) == 1
    column = result["column_classifications"][0]
    assert column["asset_id"] == "11111111-1111-4111-8111-111111111111"
    assert column["column_name"] == "email"
    assert column["classification"] == "PII_SOURCE"
    assert column["is_pii"] is True
    assert column["provenance"] == {"origin": "manual_steward", "note": "ERP customer master"}

    assert result["counts"]["quality_checks"] == 1


def test_catalog_stays_available_before_migration_0011(monkeypatch):
    class _LegacyCursor(_Cursor):
        def fetchone(self):
            if "to_regclass" in self.query:
                return {"assertions": None, "classifications": None}
            return super().fetchone()

    class _LegacyConnection(_Connection):
        def __init__(self):
            self.cur = _LegacyCursor()

    monkeypatch.setattr(search_module, "get_conn", _LegacyConnection)

    result = search_module.catalog_snapshot(Response(), limit=100, offset=0, user={"id": "user"})

    assert result["quality_checks"] == []
    assert result["column_classifications"] == []
    assert result["counts"]["quality_checks"] == 0
