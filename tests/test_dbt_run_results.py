"""
Tests for the dbt run_results.py adapter.

Covers:
  R1  Valid run_results with mixed statuses parses successfully.
  R2  success/pass statuses → RUNTIME_POSITIVE evidence_type.
  R3  error/fail statuses → RUNTIME_OBSERVED_ERROR (never RUNTIME_NEGATIVE_EVALUATION).
  R4  skip/skipped statuses → RUNTIME_SKIPPED (not evidence of non-propagation).
  R5  warn status → RUNTIME_POSITIVE with OBSERVED_EXECUTION_WITH_WARNINGS.
  R6  Empty results array → EMPTY_RUN_RESULTS diagnostic, ok=False.
  R7  Missing results key → INVALID_RUN_RESULTS_ARRAY diagnostic.
  R8  Non-object root → INVALID_ROOT diagnostic.
  R9  Result missing unique_id → error collected, rest parsed.
  R10 Counts are correct (success, error, skip, warn, total).
  R11 Payload contains invocation_id, generated_at, dbt_schema_version.
  R12 Provenance carries adapter name, version, content_sha256, filename.
  R13 never_proves sentence appears on every result.
  R14 Unsupported schema version emits UNSUPPORTED_RUN_RESULTS_SCHEMA_VERSION warning.
  R15 Missing schema version emits MISSING_RUN_RESULTS_SCHEMA_VERSION warning.
  R16 String input (pre-serialised JSON) works.
  R17 Bytes input works.
  R18 Two calls with identical input produce the same content_sha256.

Manifest version pinning (task 5):
  M1  manifest with schema version < v7 (e.g. v6) → UNSUPPORTED_DBT_MANIFEST_VERSION.
  M2  manifest with schema version v12 → parses ok.
  M3  manifest with schema version v7 → parses ok.
  M4  manifest with unknown future version (v99) → warning only, parses ok.
  M5  manifest with no schema version → MISSING_DBT_SCHEMA_VERSION warning.
  M6  parse_static_file with kind='dbt_run_results' dispatches correctly.
"""
from __future__ import annotations

import json

import pytest

from ingestion.dbt.run_results import parse_dbt_run_results
from ingestion.dbt.manifest import parse_dbt_manifest
from ingestion.static_files import parse_static_file


# ---------------------------------------------------------------------------
# Shared fixture builders
# ---------------------------------------------------------------------------

def _metadata(schema_version: str = "https://schemas.getdbt.com/dbt/run-results/v4/run-results.json") -> dict:
    return {
        "dbt_schema_version": schema_version,
        "invocation_id": "inv-abc-123",
        "generated_at": "2026-11-14T10:00:00.000Z",
    }


def _result(unique_id: str, status: str, resource_type: str = "model", execution_time: float | None = 1.0) -> dict:
    r = {"unique_id": unique_id, "status": status, "resource_type": resource_type}
    if execution_time is not None:
        r["execution_time"] = execution_time
    return r


def _full_fixture() -> dict:
    return {
        "metadata": _metadata(),
        "results": [
            _result("model.proj.revenue", "success"),
            _result("model.proj.failed_model", "error"),
            _result("test.proj.not_null_id", "pass", resource_type="test"),
            _result("test.proj.failed_test", "fail", resource_type="test"),
            _result("model.proj.skipped_model", "skip"),
            _result("model.proj.warn_model", "warn"),
        ],
    }


def _manifest_node(unique_id: str, schema_version: str = "https://schemas.getdbt.com/dbt/manifest/v12/manifest.json") -> dict:
    return {
        "metadata": {
            "dbt_schema_version": schema_version,
            "project_name": "test_proj",
        },
        "nodes": {
            unique_id: {
                "unique_id": unique_id,
                "name": unique_id.rsplit(".", 1)[-1],
                "package_name": "test_proj",
                "resource_type": "model",
                "depends_on": {"nodes": []},
            }
        },
        "sources": {},
        "exposures": {},
    }


# ===========================================================================
# run_results adapter tests
# ===========================================================================

class TestRunResultsBasic:

    def test_r1_valid_fixture_is_ok(self):
        r = parse_dbt_run_results(_full_fixture())
        assert r.ok is True
        assert r.payload is not None
        assert len(r.diagnostics) == 0

    def test_r2_success_and_pass_are_runtime_positive(self):
        r = parse_dbt_run_results(_full_fixture())
        results_by_id = {x["unique_id"]: x for x in r.payload["results"]}
        assert results_by_id["model.proj.revenue"]["evidence_type"] == "RUNTIME_POSITIVE"
        assert results_by_id["test.proj.not_null_id"]["evidence_type"] == "RUNTIME_POSITIVE"

    def test_r3_error_and_fail_are_observed_error_not_negative(self):
        """error/fail must NEVER produce RUNTIME_NEGATIVE_EVALUATION."""
        r = parse_dbt_run_results(_full_fixture())
        results_by_id = {x["unique_id"]: x for x in r.payload["results"]}
        assert results_by_id["model.proj.failed_model"]["evidence_type"] == "RUNTIME_OBSERVED_ERROR"
        assert results_by_id["test.proj.failed_test"]["evidence_type"] == "RUNTIME_OBSERVED_ERROR"
        # Explicit: never negative
        for result in r.payload["results"]:
            assert result["evidence_type"] != "RUNTIME_NEGATIVE_EVALUATION", (
                f"{result['unique_id']}: must never be RUNTIME_NEGATIVE_EVALUATION"
            )

    def test_r4_skip_is_not_executed(self):
        r = parse_dbt_run_results(_full_fixture())
        results_by_id = {x["unique_id"]: x for x in r.payload["results"]}
        assert results_by_id["model.proj.skipped_model"]["evidence_type"] == "RUNTIME_SKIPPED"
        assert results_by_id["model.proj.skipped_model"]["evidence_class"] == "NOT_EXECUTED"

    def test_r5_warn_is_runtime_positive_with_warnings_class(self):
        r = parse_dbt_run_results(_full_fixture())
        results_by_id = {x["unique_id"]: x for x in r.payload["results"]}
        assert results_by_id["model.proj.warn_model"]["evidence_type"] == "RUNTIME_POSITIVE"
        assert results_by_id["model.proj.warn_model"]["evidence_class"] == "OBSERVED_EXECUTION_WITH_WARNINGS"

    def test_r6_empty_results_returns_diagnostic(self):
        r = parse_dbt_run_results({"metadata": _metadata(), "results": []})
        assert r.ok is False
        assert r.diagnostics[0].code == "EMPTY_RUN_RESULTS"

    def test_r7_missing_results_key_returns_diagnostic(self):
        r = parse_dbt_run_results({"metadata": _metadata()})
        assert r.ok is False
        assert r.diagnostics[0].code == "INVALID_RUN_RESULTS_ARRAY"

    def test_r8_non_object_root_returns_diagnostic(self):
        r = parse_dbt_run_results([{"unique_id": "x"}])
        assert r.ok is False
        assert r.diagnostics[0].code == "INVALID_ROOT"

    def test_r9_result_missing_unique_id_produces_error(self):
        fixture = {
            "metadata": _metadata(),
            "results": [
                {"status": "success", "resource_type": "model"},   # no unique_id
                _result("model.proj.ok", "success"),
            ],
        }
        r = parse_dbt_run_results(fixture)
        # Has an error but still parses the remaining result
        assert len(r.diagnostics) > 0
        assert any(d.code == "INVALID_RUN_RESULT_UNIQUE_ID" for d in r.diagnostics)

    def test_r10_counts_are_correct(self):
        r = parse_dbt_run_results(_full_fixture())
        c = r.payload["counts"]
        assert c["success"] == 2  # success + pass
        assert c["error"] == 2    # error + fail
        assert c["skip"] == 1
        assert c["warn"] == 1
        assert c["total"] == 6

    def test_r11_payload_contains_invocation_metadata(self):
        r = parse_dbt_run_results(_full_fixture())
        assert r.payload["invocation_id"] == "inv-abc-123"
        assert r.payload["generated_at"] == "2026-11-14T10:00:00.000Z"
        assert "v4" in r.payload["dbt_schema_version"]

    def test_r12_provenance_fields_present(self):
        r = parse_dbt_run_results(_full_fixture(), filename="run_results.json")
        prov = r.payload["provenance"]
        assert prov["adapter"] == "kairos.dbt_run_results"
        assert prov["adapter_version"] == "1.0.0"
        assert len(prov["content_sha256"]) == 64  # sha256 hex
        assert prov["original_filename"] == "run_results.json"

    def test_r13_never_proves_sentence_on_every_result(self):
        r = parse_dbt_run_results(_full_fixture())
        for result in r.payload["results"]:
            assert "never_proves" in result
            assert len(result["never_proves"]) > 20

    def test_r14_unsupported_schema_version_emits_warning(self):
        fixture = {
            "metadata": {"dbt_schema_version": "https://schemas.getdbt.com/dbt/run-results/v99/run-results.json"},
            "results": [_result("model.proj.m", "success")],
        }
        r = parse_dbt_run_results(fixture)
        assert r.ok is True
        assert any(w.code == "UNSUPPORTED_RUN_RESULTS_SCHEMA_VERSION" for w in r.warnings)

    def test_r15_missing_schema_version_emits_warning(self):
        fixture = {
            "metadata": {},
            "results": [_result("model.proj.m", "success")],
        }
        r = parse_dbt_run_results(fixture)
        assert r.ok is True
        assert any(w.code == "MISSING_RUN_RESULTS_SCHEMA_VERSION" for w in r.warnings)

    def test_r16_string_input_works(self):
        r = parse_dbt_run_results(json.dumps(_full_fixture()))
        assert r.ok is True

    def test_r17_bytes_input_works(self):
        r = parse_dbt_run_results(json.dumps(_full_fixture()).encode("utf-8"))
        assert r.ok is True

    def test_r18_identical_input_same_sha256(self):
        r1 = parse_dbt_run_results(_full_fixture())
        r2 = parse_dbt_run_results(_full_fixture())
        assert r1.payload["provenance"]["content_sha256"] == r2.payload["provenance"]["content_sha256"]


# ===========================================================================
# Manifest version pinning tests (task 5)
# ===========================================================================

class TestManifestVersionPinning:

    def test_m1_v6_manifest_is_hard_rejected(self):
        r = parse_dbt_manifest({
            "metadata": {
                "dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v6/manifest.json",
                "project_name": "old_project",
            },
            "nodes": {}, "sources": {}, "exposures": {},
        })
        assert r.ok is False
        assert r.diagnostics[0].code == "UNSUPPORTED_DBT_MANIFEST_VERSION"
        assert "v6" in r.diagnostics[0].message
        assert "v7" in r.diagnostics[0].message

    @pytest.mark.parametrize("version", ["v1", "v2", "v3", "v4", "v5", "v6"])
    def test_m1_all_pre_v7_versions_are_rejected(self, version: str):
        r = parse_dbt_manifest({
            "metadata": {
                "dbt_schema_version": f"https://schemas.getdbt.com/dbt/manifest/{version}/manifest.json",
            },
            "nodes": {}, "sources": {}, "exposures": {},
        })
        assert r.ok is False
        assert r.diagnostics[0].code == "UNSUPPORTED_DBT_MANIFEST_VERSION"

    def test_m2_v12_manifest_parses_ok(self):
        r = parse_dbt_manifest(_manifest_node("model.test_proj.revenue", schema_version="https://schemas.getdbt.com/dbt/manifest/v12/manifest.json"))
        assert r.ok is True, f"Expected ok, got {r.diagnostics}"

    def test_m3_v7_manifest_parses_ok(self):
        r = parse_dbt_manifest(_manifest_node("model.test_proj.revenue", schema_version="https://schemas.getdbt.com/dbt/manifest/v7/manifest.json"))
        assert r.ok is True

    def test_m4_future_version_emits_warning_but_parses(self):
        r = parse_dbt_manifest(_manifest_node("model.test_proj.revenue", schema_version="https://schemas.getdbt.com/dbt/manifest/v99/manifest.json"))
        assert r.ok is True
        assert any(w.code == "UNTESTED_DBT_MANIFEST_VERSION" for w in r.warnings)

    def test_m5_missing_schema_version_emits_warning(self):
        r = parse_dbt_manifest({
            "metadata": {},
            "nodes": {
                "model.proj.m": {
                    "unique_id": "model.proj.m", "name": "m",
                    "package_name": "proj", "resource_type": "model",
                    "depends_on": {"nodes": []},
                }
            },
            "sources": {}, "exposures": {},
        })
        assert r.ok is True
        assert any(w.code == "MISSING_DBT_SCHEMA_VERSION" for w in r.warnings)


# ===========================================================================
# Static file dispatch test
# ===========================================================================

class TestStaticFileDispatch:

    def test_m6_dbt_run_results_kind_dispatches(self):
        """parse_static_file('dbt_run_results', ...) must route to the adapter."""
        r = parse_static_file(
            "dbt_run_results",
            _full_fixture(),
            filename="run_results.json",
        )
        assert r.ok is True
        assert r.payload is not None
        assert r.payload.get("kind") == "dbt_run_results"

    def test_unsupported_kind_returns_diagnostic(self):
        r = parse_static_file("unknown_format", {})
        assert r.ok is False
        assert r.diagnostics[0].code == "UNSUPPORTED_STATIC_FILE_KIND"
        assert "dbt_run_results" in r.diagnostics[0].message
