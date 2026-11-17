"""Pure dbt run_results.json adapter for the Kairos ingestion contract.

What this adapter does
──────────────────────
A dbt ``run_results.json`` file records which models, seeds, snapshots and
tests *executed* in a specific dbt invocation, their completion status, and
timing.  This adapter reads those outcomes and emits OBSERVED evidence for
assets that **completed successfully** in this invocation.

What it does NOT claim
──────────────────────
  - A model succeeding in a dbt run is NOT proof that every declared
    ``depends_on`` edge was active in that run.  Propagation evidence
    requires OpenLineage or SQLGlot.
  - A test passing is proof the test ran and found nothing wrong; it is NOT
    proof that the upstream lineage is correct.
  - A model in ERROR or SKIPPED state does NOT create negative evidence —
    absence of execution is not evidence of absence.

Output format
──────────────
Returns a ``MetadataGraphResult`` whose payload is NOT a ``kairos.ingest.v1``
graph envelope (run_results produce evidence rows, not asset/relationship
declarations).  Instead, the payload contains:

  {
    "kind": "dbt_run_results",
    "adapter_version": "1.0.0",
    "invocation_id": "...",
    "generated_at": "...",
    "dbt_schema_version": "...",
    "results": [
      {
        "unique_id": "model.project.name",
        "node_name": "...",
        "resource_type": "model",
        "status": "success",
        "execution_time_seconds": 1.23,
        "evidence_type": "RUNTIME_POSITIVE",
        "evidence_class": "OBSERVED_EXECUTION",
        "never_proves": "that every declared dependency was active in this run"
      },
      ...
    ],
    "counts": {"success": N, "error": N, "skip": N, "warn": N, "total": N},
    "provenance": {
      "adapter": "kairos.dbt_run_results",
      "adapter_version": "1.0.0",
      "content_sha256": "...",
      "original_filename": "..."
    }
  }

The caller (ingest route) stores this payload as a raw event and may create
evidence rows from ``results[*]`` where ``evidence_type == "RUNTIME_POSITIVE"``.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from ingestion.metadata_graph import (
    MAX_FILE_BYTES,
    _DuplicateJSONKey,
    Diagnostic,
    MetadataGraphResult,
    _canonical_json,
    _count_and_check_json,
    _reject_duplicate_keys,
)

ADAPTER_VERSION = "1.0.0"

# dbt status values that mean the node executed and completed without error.
_SUCCESS_STATUSES = frozenset({"success", "pass"})
# dbt status values that mean the node ran but encountered an error/warning.
_ERROR_STATUSES = frozenset({"error", "fail", "runtime error"})
# Skipped/deselected nodes did not execute; they produce no evidence.
_SKIP_STATUSES = frozenset({"skip", "skipped", "partial success"})

# Resource types we care about from run_results.
_SUPPORTED_RESOURCE_TYPES = frozenset({"model", "seed", "snapshot", "test", "analysis"})

# Supported dbt run_results schema versions.
# https://schemas.getdbt.com/dbt/run-results/v*/manifest.json
_SUPPORTED_SCHEMA_VERSIONS = {"v2", "v3", "v4", "v5", "v6"}
_SCHEMA_VERSION_PREFIX = "https://schemas.getdbt.com/dbt/run-results/"

_NEVER_PROVES = (
    "that every declared dependency edge was active in this run, "
    "that any column-level propagation occurred, "
    "or that the produced data is correct. "
    "Runtime propagation evidence requires OpenLineage events."
)


def _load(source: bytes | str | Mapping[str, Any]) -> tuple[dict[str, Any] | None, bytes | None, Diagnostic | None]:
    """Load and decode the source into a dict.  Returns (document, raw_bytes, error)."""
    if isinstance(source, bytes):
        raw = source
        if len(raw) > MAX_FILE_BYTES:
            return None, None, Diagnostic("FILE_TOO_LARGE",
                f"File exceeds the {MAX_FILE_BYTES // (1024 * 1024)} MiB limit.")
        try:
            document = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_reject_duplicate_keys)
        except _DuplicateJSONKey as exc:
            return None, None, Diagnostic("DUPLICATE_JSON_KEY", str(exc))
        except (ValueError, UnicodeDecodeError, RecursionError) as exc:
            return None, None, Diagnostic("INVALID_JSON", f"Could not parse UTF-8 JSON: {exc}")
    elif isinstance(source, str):
        try:
            raw = source.encode("utf-8")
            document = json.loads(source, object_pairs_hook=_reject_duplicate_keys)
        except _DuplicateJSONKey as exc:
            return None, None, Diagnostic("DUPLICATE_JSON_KEY", str(exc))
        except (UnicodeEncodeError, ValueError, RecursionError) as exc:
            return None, None, Diagnostic("INVALID_JSON", f"Could not parse run_results JSON: {exc}")
        if len(raw) > MAX_FILE_BYTES:
            return None, None, Diagnostic("FILE_TOO_LARGE",
                f"File exceeds the {MAX_FILE_BYTES // (1024 * 1024)} MiB limit.")
    elif isinstance(source, Mapping):
        try:
            raw = _canonical_json(dict(source))
            document = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
        except _DuplicateJSONKey as exc:
            return None, None, Diagnostic("DUPLICATE_JSON_KEY", str(exc))
        except (TypeError, ValueError, RecursionError) as exc:
            return None, None, Diagnostic("INVALID_JSON_VALUE",
                f"run_results must contain JSON-compatible values: {exc}")
        if len(raw) > MAX_FILE_BYTES:
            return None, None, Diagnostic("FILE_TOO_LARGE",
                f"File exceeds the {MAX_FILE_BYTES // (1024 * 1024)} MiB limit.")
    else:
        return None, None, Diagnostic("INVALID_ROOT", "dbt run_results must be a JSON object.")
    if not isinstance(document, dict):
        return None, None, Diagnostic("INVALID_ROOT", "dbt run_results must be a JSON object.")
    return document, raw, None


def parse_dbt_run_results(
    source: bytes | str | Mapping[str, Any],
    *,
    filename: str = "run_results.json",
) -> MetadataGraphResult:
    """Parse a dbt ``run_results.json`` into evidence records.

    Returns a ``MetadataGraphResult`` whose payload is a ``dbt_run_results``
    document (not a ``kairos.ingest.v1`` envelope).  The ``ok`` flag is True
    when at least one result was successfully parsed; warnings carry
    version/format issues that did not block parsing.

    Callers must not store the ``payload`` as a lineage graph — use it to
    create evidence rows tagged ``evidence_type=RUNTIME_POSITIVE``.
    """
    document, raw, load_error = _load(source)
    if load_error:
        return MetadataGraphResult(None, (load_error,))
    assert document is not None and raw is not None

    errors: list[Diagnostic] = []
    warnings: list[Diagnostic] = []

    _count_and_check_json(document, errors)
    if errors:
        return MetadataGraphResult(None, tuple(errors))

    # ── Schema version ────────────────────────────────────────────────────
    schema_url = document.get("metadata", {}).get("dbt_schema_version", "")
    if not isinstance(schema_url, str) or not schema_url.strip():
        warnings.append(Diagnostic(
            "MISSING_RUN_RESULTS_SCHEMA_VERSION",
            "metadata.dbt_schema_version is absent; the run_results format could not be verified.",
            "metadata.dbt_schema_version",
        ))
    else:
        version_found = False
        for v in _SUPPORTED_SCHEMA_VERSIONS:
            if v in schema_url:
                version_found = True
                break
        if not version_found:
            warnings.append(Diagnostic(
                "UNSUPPORTED_RUN_RESULTS_SCHEMA_VERSION",
                f"dbt_schema_version {schema_url!r} is not in the tested set "
                f"({', '.join(sorted(_SUPPORTED_SCHEMA_VERSIONS))}). "
                "Results were parsed conservatively; some fields may be missing.",
                "metadata.dbt_schema_version",
            ))

    # ── Invocation metadata ───────────────────────────────────────────────
    metadata = document.get("metadata", {})
    if not isinstance(metadata, dict):
        errors.append(Diagnostic("INVALID_RUN_RESULTS_METADATA",
            "metadata must be an object.", "metadata"))
        return MetadataGraphResult(None, tuple(errors))

    invocation_id = metadata.get("invocation_id")
    generated_at = metadata.get("generated_at")
    dbt_schema_version = metadata.get("dbt_schema_version")

    # ── Results array ─────────────────────────────────────────────────────
    raw_results = document.get("results")
    if not isinstance(raw_results, list):
        errors.append(Diagnostic("INVALID_RUN_RESULTS_ARRAY",
            "results must be an array.", "results"))
        return MetadataGraphResult(None, tuple(errors))

    if not raw_results:
        return MetadataGraphResult(None, (
            Diagnostic("EMPTY_RUN_RESULTS",
                "run_results.json contains no results; nothing to ingest."),
        ))

    # ── Parse each result ─────────────────────────────────────────────────
    parsed_results: list[dict[str, Any]] = []
    counts: dict[str, int] = {"success": 0, "error": 0, "skip": 0, "warn": 0, "total": 0}

    for index, raw_result in enumerate(raw_results):
        path = f"results[{index}]"
        if not isinstance(raw_result, dict):
            errors.append(Diagnostic("INVALID_RUN_RESULT",
                "Each result must be an object.", path))
            continue

        # unique_id is the primary key; fall back to node.unique_id for older formats
        unique_id = raw_result.get("unique_id")
        if not unique_id:
            node = raw_result.get("node", {})
            unique_id = node.get("unique_id") if isinstance(node, dict) else None
        if not isinstance(unique_id, str) or not unique_id.strip():
            errors.append(Diagnostic("INVALID_RUN_RESULT_UNIQUE_ID",
                "Result must have a unique_id string.", f"{path}.unique_id"))
            continue
        unique_id = unique_id.strip()

        # Resource type
        resource_type = raw_result.get("resource_type") or unique_id.split(".")[0]
        if not isinstance(resource_type, str):
            resource_type = "unknown"
        resource_type = resource_type.strip().lower()

        # Status — dbt uses "success", "error", "skip", "warn", "pass", "fail"
        status_raw = raw_result.get("status", "")
        if not isinstance(status_raw, str):
            status_raw = ""
        status = status_raw.strip().lower()

        # Execution time
        exec_time = raw_result.get("execution_time")
        if not isinstance(exec_time, (int, float)) or exec_time < 0:
            exec_time = None

        # Determine evidence type
        # Only COMPLETED (success/pass) nodes produce positive evidence.
        # ERROR/FAIL nodes do NOT produce negative evidence (absence ≠ refutation).
        # SKIP nodes produce no evidence of any kind.
        if status in _SUCCESS_STATUSES:
            evidence_type = "RUNTIME_POSITIVE"
            evidence_class = "OBSERVED_EXECUTION"
            counts["success"] += 1
        elif status in _ERROR_STATUSES:
            # Store the fact that the node was attempted and failed — this is
            # observational metadata, not a lineage refutation.
            evidence_type = "RUNTIME_OBSERVED_ERROR"
            evidence_class = "OBSERVED_EXECUTION_ERROR"
            counts["error"] += 1
        elif status in _SKIP_STATUSES:
            evidence_type = "RUNTIME_SKIPPED"
            evidence_class = "NOT_EXECUTED"
            counts["skip"] += 1
        elif status == "warn":
            evidence_type = "RUNTIME_POSITIVE"
            evidence_class = "OBSERVED_EXECUTION_WITH_WARNINGS"
            counts["warn"] += 1
        else:
            # Unknown status — store as metadata only, no evidence classification
            evidence_type = "RUNTIME_UNKNOWN_STATUS"
            evidence_class = "UNKNOWN"
            counts["skip"] += 1

        counts["total"] += 1

        # Node name for display
        node_name = raw_result.get("node_name") or unique_id.rsplit(".", 1)[-1]

        parsed_results.append({
            "unique_id": unique_id,
            "node_name": node_name,
            "resource_type": resource_type,
            "status": status,
            "execution_time_seconds": exec_time,
            "evidence_type": evidence_type,
            "evidence_class": evidence_class,
            "never_proves": _NEVER_PROVES,
        })

    if errors:
        return MetadataGraphResult(None, tuple(errors))

    if not parsed_results:
        return MetadataGraphResult(None, (
            Diagnostic("NO_PARSEABLE_RESULTS",
                "No results could be parsed from run_results.json."),
        ))

    content_sha256 = hashlib.sha256(raw).hexdigest()

    payload: dict[str, Any] = {
        "kind": "dbt_run_results",
        "adapter_version": ADAPTER_VERSION,
        "invocation_id": invocation_id,
        "generated_at": generated_at,
        "dbt_schema_version": dbt_schema_version,
        "results": parsed_results,
        "counts": counts,
        "provenance": {
            "adapter": "kairos.dbt_run_results",
            "adapter_version": ADAPTER_VERSION,
            "content_sha256": content_sha256,
            "original_filename": filename,
        },
    }

    return MetadataGraphResult(payload, (), tuple(warnings))
