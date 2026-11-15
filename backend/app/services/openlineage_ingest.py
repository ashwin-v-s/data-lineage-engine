"""Workspace-scoped OpenLineage event ingestion.

The code path this module implements, end to end:

    request body
      -> validation (run.runId, job.name, eventType, eventTime)
      -> normalization (identities, event status, coverage manifest)
      -> PostgreSQL persistence
             raw_event            immutable copy of the delivered event
             job / execution_run  the run this event belongs to
             dataset              canonical in/out assets (workspace scoped)
             evidence             RUNTIME_POSITIVE at DATASET granularity
             lineage_edge         observed source -> target relationship
             edge_temporal_version  bitemporal attachment of that evidence
      -> authorized readback through /lineage/edges/{id}/evidence

Hard rules (Architecture Pack §12)
----------------------------------
1. Every accepted event is stored once in ``raw_event``. Replays are no-ops.
2. Only COMPLETE events produce RUNTIME_POSITIVE evidence. START, RUNNING,
   FAIL, ABORT and OTHER events are stored but never become evidence.
3. Absence is never stored: there is no "missing event" row and no negative
   evidence unless a producer explicitly sends one.
4. No cartesian claim. Evidence is written per (input, output) pair because the
   job boundary was observed. A dataset-level edge is only created when the
   event names exactly one output, which makes "these inputs fed that output"
   the observed boundary rather than a guess. With several outputs the event
   cannot say which input fed which output, so no edges are created and a
   diagnostic records why.
5. Event identifiers are prefixed with the workspace so two tenants may deliver
   the same producer event id without colliding on the global raw_event key.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Iterable, Mapping, Sequence

ALLOWED_EVENT_TYPES = ("START", "RUNNING", "COMPLETE", "ABORT", "FAIL", "OTHER")
TERMINAL_EVENT_TYPES = frozenset({"COMPLETE", "ABORT", "FAIL"})
MAX_BATCH_SIZE = 100
SOURCE_SYSTEM = "openlineage"
EDGE_OPERATOR = "openlineage:dataset_boundary"


def payload_hash(event: Mapping[str, Any]) -> str:
    canonical = json.dumps(event, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def event_identifier(event: Mapping[str, Any]) -> str:
    """Producer event id when present, otherwise a deterministic payload hash."""
    explicit = event.get("eventId") or event.get("eventID") or ""
    text = str(explicit).strip()
    return text or payload_hash(event)


def canonical_event_type(value: Any) -> tuple[str, list[str]]:
    text = str(value or "").strip().upper()
    if not text:
        return "OTHER", ["missing_event_type"]
    if text not in ALLOWED_EVENT_TYPES:
        return "OTHER", [f"unknown_event_type:{text}"]
    return text, []


def run_status_for(event_type: str) -> str:
    if event_type == "COMPLETE":
        return "completed"
    if event_type in {"ABORT", "FAIL"}:
        return "failed"
    return "running"


def parse_event_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _database_from_namespace(namespace: Any) -> str:
    text = str(namespace or "").strip()
    if "://" in text:
        tail = text.split("://", 1)[1]
        if "/" in tail:
            return tail.rsplit("/", 1)[1] or SOURCE_SYSTEM
        return tail or SOURCE_SYSTEM
    return text or SOURCE_SYSTEM


def dataset_identity(namespace: Any, name: Any) -> dict[str, str]:
    """Split an OpenLineage dataset name into canonical dataset components.

    ``analytics.orders`` becomes schema=analytics, name=orders. A three-part
    name keeps its database. A bare name keeps an empty schema so it can still
    be matched against a catalog asset by name.
    """
    raw = str(name or "").strip()
    parts = [part for part in raw.split(".") if part]
    database = _database_from_namespace(namespace)
    if len(parts) >= 3:
        return {"database_name": parts[-3], "schema_name": parts[-2], "name": parts[-1]}
    if len(parts) == 2:
        return {"database_name": database, "schema_name": parts[0], "name": parts[1]}
    return {"database_name": database, "schema_name": "", "name": raw}


def _dataset_summary(dataset: Any) -> dict[str, str]:
    if not isinstance(dataset, Mapping):
        return {"namespace": "", "name": "", "schema": "", "table": ""}
    identity = dataset_identity(dataset.get("namespace"), dataset.get("name"))
    return {
        "namespace": str(dataset.get("namespace") or ""),
        "name": str(dataset.get("name") or ""),
        "schema": identity["schema_name"],
        "table": identity["name"],
    }


def summarize_event(event: Any) -> dict[str, Any]:
    """Validate and describe one event without touching the database."""
    if not isinstance(event, Mapping):
        return {
            "valid": False,
            "eventType": "OTHER",
            "eventTime": None,
            "producer": None,
            "job": {"namespace": "", "name": ""},
            "runId": "",
            "inputs": [],
            "outputs": [],
            "warnings": ["The event is not a JSON object."],
        }

    warnings: list[str] = []
    run = event.get("run") if isinstance(event.get("run"), Mapping) else {}
    job = event.get("job") if isinstance(event.get("job"), Mapping) else {}
    run_id = str(run.get("runId") or "").strip()
    job_name = str(job.get("name") or "").strip()
    event_type, type_warnings = canonical_event_type(event.get("eventType"))
    warnings.extend(type_warnings)
    if not run_id:
        warnings.append("run.runId is required and must not be empty.")
    if not job_name:
        warnings.append("job.name is required and must not be empty.")

    raw_time = event.get("eventTime")
    event_time = parse_event_time(raw_time)
    if event_time is None:
        warnings.append("eventTime is missing or not an ISO-8601 timestamp.")

    raw_inputs = event.get("inputs")
    raw_outputs = event.get("outputs")
    inputs = [_dataset_summary(item) for item in raw_inputs] if isinstance(raw_inputs, list) else []
    outputs = [_dataset_summary(item) for item in raw_outputs] if isinstance(raw_outputs, list) else []
    for collection, label in ((inputs, "input"), (outputs, "output")):
        if any(not item["name"] for item in collection):
            warnings.append(f"An {label} dataset has no name and will be skipped.")

    if event_type == "COMPLETE" and (not inputs or not outputs):
        warnings.append(
            "A COMPLETE event without both inputs and outputs cannot produce "
            "runtime evidence."
        )

    return {
        "valid": bool(run_id and job_name),
        "eventType": event_type,
        "eventTime": event_time.isoformat() if event_time else (str(raw_time) if raw_time else None),
        "producer": str(event.get("producer") or "") or None,
        "job": {"namespace": str(job.get("namespace") or ""), "name": job_name},
        "runId": run_id,
        "inputs": inputs,
        "outputs": outputs,
        "warnings": warnings,
    }


def summarize_batch(raw_events: Sequence[Any]) -> dict[str, Any]:
    summaries = [summarize_event(event) for event in raw_events]
    warnings: list[str] = []
    for index, summary in enumerate(summaries, start=1):
        warnings.extend(f"Event {index}: {warning}" for warning in summary["warnings"])
    return {
        "events": summaries,
        "count": len(summaries),
        "valid_count": sum(1 for summary in summaries if summary["valid"]),
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _workspace_id(cur) -> str:
    cur.execute("SELECT NULLIF(current_setting('kairos.workspace_id', true), '') AS workspace_id")
    row = cur.fetchone()
    if isinstance(row, Mapping):
        value = row.get("workspace_id")
    elif row:
        value = row[0]
    else:
        value = None
    if not value:
        raise RuntimeError("Authenticated workspace context is missing")
    return str(value)


def _insert_raw_event(cur, raw_id: str, event: Mapping[str, Any], digest: str) -> bool:
    cur.execute(
        """
        INSERT INTO raw_event (event_id, payload, payload_hash, source_system)
        VALUES (%s, %s::jsonb, %s, 'openlineage')
        ON CONFLICT (event_id) DO NOTHING
        """,
        (raw_id, json.dumps(event), digest),
    )
    return cur.rowcount == 1


def _upsert_job(cur, namespace: str, name: str) -> str:
    cur.execute(
        """
        INSERT INTO job (namespace, name)
        VALUES (%s, %s)
        ON CONFLICT (workspace_id, namespace, name)
        DO UPDATE SET name = EXCLUDED.name
        RETURNING id::text AS id
        """,
        (namespace, name),
    )
    return str(cur.fetchone()["id"])


def _upsert_run(
    cur,
    run_id: str,
    job_id: str,
    status: str,
    started_at: datetime | None,
    completed_at: datetime | None,
) -> str:
    """Upsert the run without letting a late START reopen a terminal run."""
    cur.execute(
        """
        INSERT INTO execution_run (run_id, job_id, status, started_at, completed_at)
        VALUES (%s, %s::uuid, %s, %s, %s)
        ON CONFLICT (workspace_id, run_id) DO UPDATE SET
            job_id = EXCLUDED.job_id,
            status = CASE
                WHEN execution_run.status IN ('completed', 'failed')
                 AND EXCLUDED.status = 'running'
                THEN execution_run.status
                ELSE EXCLUDED.status
            END,
            started_at = COALESCE(execution_run.started_at, EXCLUDED.started_at),
            completed_at = COALESCE(EXCLUDED.completed_at, execution_run.completed_at)
        RETURNING id::text AS id
        """,
        (run_id, job_id, status, started_at, completed_at),
    )
    return str(cur.fetchone()["id"])


def _resolve_dataset(cur, namespace: str, name: str) -> str | None:
    """Match an existing canonical asset, else create one for the event."""
    identity = dataset_identity(namespace, name)
    if not identity["name"]:
        return None
    cur.execute(
        """
        SELECT id::text AS id
        FROM dataset
        WHERE name = %s
          AND (%s = '' OR schema_name = %s)
        ORDER BY (source_system = 'openlineage') ASC, created_at DESC
        LIMIT 1
        """,
        (identity["name"], identity["schema_name"], identity["schema_name"]),
    )
    row = cur.fetchone()
    if row:
        return str(row["id"])
    cur.execute(
        """
        INSERT INTO dataset
            (source_system, namespace, database_name, schema_name, name, asset_type)
        VALUES ('openlineage', %s, %s, %s, %s, 'table')
        ON CONFLICT (workspace_id, source_system, namespace, database_name, schema_name, name, asset_type)
        DO UPDATE SET name = EXCLUDED.name
        RETURNING id::text AS id
        """,
        (
            str(namespace or SOURCE_SYSTEM),
            identity["database_name"],
            identity["schema_name"],
            identity["name"],
        ),
    )
    row = cur.fetchone()
    return str(row["id"]) if row else None


def runtime_coverage_manifest(
    source_covered: bool,
    target_covered: bool,
    *,
    column_lineage_parsed: bool,
) -> dict[str, Any]:
    """Coverage of a dataset-boundary observation, stated at its own scope."""
    return {
        "coverage_mode": "runtime",
        "parser_status": "SUPPORTED" if column_lineage_parsed else "PARTIAL",
        "scope": "DATASET",
        "run_covered": True,
        "operator_covered": False,
        "source_dataset_covered": source_covered,
        "target_dataset_covered": target_covered,
        "source_columns_covered": [],
        "target_columns_covered": [],
        "branches_covered": False,
        "column_lineage_parsed": column_lineage_parsed,
        "note": (
            "Dataset boundary observation. The COMPLETE event proves the job read the "
            "source and wrote the target; operator, branch and column scope are not "
            "claimed and are not treated as missing at DATASET granularity."
        ),
    }


def _insert_runtime_evidence(
    cur,
    *,
    evidence_id: str,
    run_id: str,
    event_time: datetime | None,
    source_dataset_id: str,
    target_dataset_id: str,
    raw_event_id: str,
    diagnostics: Sequence[str],
    column_lineage_parsed: bool,
) -> str | None:
    """Insert RUNTIME_POSITIVE evidence; return its row id when newly written."""
    coverage = runtime_coverage_manifest(
        True, True, column_lineage_parsed=column_lineage_parsed
    )
    cur.execute(
        """
        INSERT INTO evidence (
            evidence_id, evidence_type, source_system, run_id, source_dataset_id,
            target_dataset_id, granularity, parser_status, coverage, event_time,
            effective_time, ingestion_time, diagnostics, raw_event_id
        )
        VALUES (%s, 'RUNTIME_POSITIVE', 'openlineage', %s, %s::uuid, %s::uuid,
                'DATASET', %s, %s::jsonb, %s, %s, now(), %s::jsonb, %s)
        ON CONFLICT (workspace_id, evidence_id) DO NOTHING
        RETURNING id::text AS id
        """,
        (
            evidence_id,
            run_id,
            source_dataset_id,
            target_dataset_id,
            coverage["parser_status"],
            json.dumps(coverage),
            event_time,
            event_time,
            json.dumps({"diagnostics": list(diagnostics), "classification": "RUNTIME_OBSERVED"}),
            raw_event_id,
        ),
    )
    row = cur.fetchone()
    return str(row["id"]) if row else None


def _ensure_edge(
    cur,
    *,
    workspace_id: str,
    source_dataset_id: str,
    target_dataset_id: str,
    evidence_row_id: str,
    event_time: datetime | None,
) -> tuple[str, bool]:
    """Return the dataset edge and whether this call created it.

    An advisory lock keyed on the workspace and the edge identity keeps a
    concurrent replay from inserting a second logical edge, whose unique index
    would not catch a NULL query fingerprint.
    """
    cur.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
        (f"{workspace_id}:{source_dataset_id}:{target_dataset_id}:{EDGE_OPERATOR}",),
    )
    cur.execute(
        """
        SELECT id::text AS id
        FROM lineage_edge
        WHERE source_id = %s::uuid
          AND target_id = %s::uuid
          AND granularity = 'DATASET'
          AND operator_fingerprint = %s
        LIMIT 1
        """,
        (source_dataset_id, target_dataset_id, EDGE_OPERATOR),
    )
    row = cur.fetchone()
    created = False
    if row:
        edge_id = str(row["id"])
    else:
        cur.execute(
            """
            INSERT INTO lineage_edge
                (source_id, target_id, granularity, operator_fingerprint)
            VALUES (%s::uuid, %s::uuid, 'DATASET', %s)
            RETURNING id::text AS id
            """,
            (source_dataset_id, target_dataset_id, EDGE_OPERATOR),
        )
        edge_id = str(cur.fetchone()["id"])
        created = True

    cur.execute(
        """
        SELECT 1 AS present
        FROM edge_temporal_version
        WHERE edge_id = %s::uuid AND evidence_id = %s::uuid
        LIMIT 1
        """,
        (edge_id, evidence_row_id),
    )
    if cur.fetchone() is None:
        cur.execute(
            """
            INSERT INTO edge_temporal_version
                (edge_id, valid_from, effective_time_status, transaction_from,
                 evidence_id, source_system)
            VALUES (%s::uuid, COALESCE(%s, now()), %s, now(), %s::uuid, 'openlineage')
            """,
            (
                edge_id,
                event_time,
                "KNOWN" if event_time is not None else "UNKNOWN",
                evidence_row_id,
            ),
        )
    return edge_id, created


def _named_datasets(event: Mapping[str, Any], field: str) -> list[tuple[str, str]]:
    raw = event.get(field)
    if not isinstance(raw, list):
        return []
    result: list[tuple[str, str]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        result.append((str(item.get("namespace") or ""), name))
    return result


def _column_lineage_present(event: Mapping[str, Any]) -> bool:
    outputs = event.get("outputs")
    if not isinstance(outputs, list):
        return False
    for output in outputs:
        if not isinstance(output, Mapping):
            continue
        facets = output.get("facets")
        if isinstance(facets, Mapping) and facets.get("columnLineage"):
            return True
    return False


def ingest_one_event(cur, event: Mapping[str, Any], summary: Mapping[str, Any]) -> dict[str, Any]:
    """Persist one validated event. Returns per-event counters and diagnostics."""
    outcome = {
        "accepted": 0,
        "duplicate": 0,
        "skipped": 0,
        "evidence_created": 0,
        "edges_created": 0,
        "runs_written": 0,
        "diagnostics": list(summary.get("warnings") or []),
    }
    workspace_id = _workspace_id(cur)
    raw_id = f"ol:{workspace_id}:{event_identifier(event)}"

    if not _insert_raw_event(cur, raw_id, event, payload_hash(event)):
        outcome["duplicate"] = 1
        outcome["diagnostics"].append("Duplicate event payload; no rows were written.")
        return outcome

    outcome["accepted"] = 1
    job = summary.get("job") or {}
    job_id = _upsert_job(
        cur, str(job.get("namespace") or SOURCE_SYSTEM), str(job.get("name") or ""),
    )
    event_type = str(summary.get("eventType") or "OTHER")
    event_time = parse_event_time(summary.get("eventTime"))
    _upsert_run(
        cur,
        str(summary.get("runId") or ""),
        job_id,
        run_status_for(event_type),
        event_time if event_type in {"START", "RUNNING"} else None,
        event_time if event_type in TERMINAL_EVENT_TYPES else None,
    )
    outcome["runs_written"] = 1

    if event_type != "COMPLETE":
        outcome["diagnostics"].append(
            f"non_complete_event:{event_type} — raw event and run stored, no evidence written"
        )
        return outcome

    inputs = _named_datasets(event, "inputs")
    outputs = _named_datasets(event, "outputs")
    if not inputs or not outputs:
        outcome["diagnostics"].append(
            "complete_event_has_no_inputs_or_outputs — no evidence written"
        )
        return outcome

    column_lineage_parsed = _column_lineage_present(event)
    if column_lineage_parsed:
        outcome["diagnostics"].append(
            "columnLineage_facet_detected — the facet is preserved in the raw event but "
            "is not parsed yet; dataset-level evidence is written"
        )

    resolved_inputs: list[tuple[str, str]] = []
    for namespace, name in inputs:
        dataset_id = _resolve_dataset(cur, namespace, name)
        if dataset_id:
            resolved_inputs.append((name, dataset_id))
        else:
            outcome["diagnostics"].append(f"failed_to_upsert_input_dataset:{name}")

    resolved_outputs: list[tuple[str, str]] = []
    for namespace, name in outputs:
        dataset_id = _resolve_dataset(cur, namespace, name)
        if dataset_id:
            resolved_outputs.append((name, dataset_id))
        else:
            outcome["diagnostics"].append(f"failed_to_upsert_output_dataset:{name}")

    run_id = str(summary.get("runId") or "")
    evidence_row_ids: dict[tuple[str, str], str] = {}
    for input_name, source_id in resolved_inputs:
        for output_name, target_id in resolved_outputs:
            evidence_id = f"ol:{workspace_id}:{run_id}:{source_id}:{target_id}"
            evidence_row_id = _insert_runtime_evidence(
                cur,
                evidence_id=evidence_id,
                run_id=run_id,
                event_time=event_time,
                source_dataset_id=source_id,
                target_dataset_id=target_id,
                raw_event_id=raw_id,
                diagnostics=[f"input:{input_name}", f"output:{output_name}"],
                column_lineage_parsed=column_lineage_parsed,
            )
            if evidence_row_id:
                outcome["evidence_created"] += 1
                evidence_row_ids[(source_id, target_id)] = evidence_row_id

    if len(resolved_inputs) and len(resolved_outputs) == 1:
        target_id = resolved_outputs[0][1]
        for _input_name, source_id in resolved_inputs:
            evidence_row_id = evidence_row_ids.get((source_id, target_id))
            if not evidence_row_id:
                # The evidence row already existed (replayed run with a new
                # event id). Reuse it instead of dropping the relationship.
                evidence_id = f"ol:{workspace_id}:{run_id}:{source_id}:{target_id}"
                cur.execute(
                    "SELECT id::text AS id FROM evidence WHERE evidence_id = %s LIMIT 1",
                    (evidence_id,),
                )
                evidence_row = cur.fetchone()
                if not evidence_row:
                    outcome["diagnostics"].append(
                        f"edge_not_created:no_evidence_row:{source_id}->{target_id}"
                    )
                    continue
                evidence_row_id = str(evidence_row["id"])
            _edge_id, created = _ensure_edge(
                cur,
                workspace_id=workspace_id,
                source_dataset_id=source_id,
                target_dataset_id=target_id,
                evidence_row_id=evidence_row_id,
                event_time=event_time,
            )
            outcome["edges_created"] += 1 if created else 0
    elif len(resolved_outputs) > 1:
        outcome["diagnostics"].append(
            "multiple_outputs — observed inputs and outputs cannot be paired, so no "
            "dataset-level edges were created; evidence is stored per pair"
        )

    return outcome


def ingest_openlineage_events(cur, raw_events: Iterable[Any]) -> dict[str, Any]:
    """Ingest a batch, returning aggregate counters and diagnostics."""
    totals: dict[str, Any] = {
        "accepted": 0,
        "duplicate": 0,
        "skipped": 0,
        "evidence_created": 0,
        "edges_created": 0,
        "runs_written": 0,
        "diagnostics": [],
    }
    for index, event in enumerate(raw_events, start=1):
        if not isinstance(event, Mapping):
            totals["skipped"] += 1
            totals["diagnostics"].append(f"Event {index}: skipped non-object entry in batch.")
            continue
        summary = summarize_event(event)
        if not summary["valid"]:
            totals["skipped"] += 1
            totals["diagnostics"].extend(
                f"Event {index}: {warning}" for warning in summary["warnings"]
            )
            continue
        outcome = ingest_one_event(cur, event, summary)
        for key in ("accepted", "duplicate", "skipped", "evidence_created",
                    "edges_created", "runs_written"):
            totals[key] += outcome[key]
        totals["diagnostics"].extend(
            f"Event {index}: {message}" for message in outcome["diagnostics"]
        )
    return totals
