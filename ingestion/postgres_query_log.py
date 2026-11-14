"""PostgreSQL query-log capture adapter for the Kairos ingestion contract.

What this adapter does
──────────────────────
Parses a list of PostgreSQL query-log records (from pg_stat_statements or a
pg_log export) and emits *at best* POSSIBLE lineage candidates.

Each log record is a SQL statement that was executed on the source database.
The adapter runs the SQL through SQLGlot to extract table references, then
produces ``sql_static_candidate`` relationship records with the evidence class
``POSSIBLE`` and an explicit ``never_proves`` sentence.

What it does NOT claim
──────────────────────
  - A query appearing in the log does NOT prove that any column-level
    dependency was active.  It proves only that the statement ran.
  - The adapter never emits ``OBSERVED`` or ``RUNTIME_POSITIVE`` evidence.
    Log-derived lineage is structural/static analysis of past statements,
    not observation of a specific run with known inputs/outputs.
  - Duplicate queries and queries without a declared target (plain SELECT)
    produce no relationship records.

Security contract (Architecture v2 §9.4 / §11 D8)
──────────────────────────────────────────────────
  This adapter is **opt-in only**.  The scope flag
  ``postgres_query_log`` must be explicitly granted by the workspace owner
  before any query log is ingested.  Kairos never automatically captures
  query logs — the user must supply the log data explicitly.

  The ``never_proves`` sentence is mandatory on every result and must appear
  in any UI that renders query-log lineage.

Output
──────
Returns a ``MetadataGraphResult`` with a ``kairos.ingest.v1`` envelope where:
  - Every relationship has ``edge_type = "sql_static_candidate"``
  - Every relationship has ``evidence_class = "POSSIBLE"``
  - ``provenance.adapter = "kairos.postgres_query_log"``
  - ``provenance.never_proves`` is set on the payload
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

try:
    import sqlglot
    from sqlglot import exp as _exp
    _SQLGLOT_AVAILABLE = True
except ImportError:
    _SQLGLOT_AVAILABLE = False

from ingestion.metadata_graph import (
    CONTRACT_VERSION,
    MAX_FILE_BYTES,
    Diagnostic,
    MetadataGraphResult,
    _canonical_json,
)

ADAPTER_VERSION = "1.0.0"

NEVER_PROVES = (
    "that any specific data value was read or written, "
    "that a dependency was active in any particular run, "
    "or that the query produced correct results. "
    "Query-log lineage is POSSIBLE evidence from past statement text, "
    "not OBSERVED evidence from a specific execution."
)

# Maximum number of query records accepted per call.
MAX_QUERY_RECORDS = 500

# Maximum SQL text length per record (longer queries are truncated before parsing).
MAX_SQL_LENGTH = 10_000


def _table_name(table: Any) -> str:
    """Extract qualified table name from a sqlglot Table expression."""
    return ".".join(part.name for part in table.parts if part.name)


def _extract_tables_from_sql(sql: str, dialect: str = "postgres") -> tuple[list[str], str | None]:
    """
    Parse one SQL statement and return (source_tables, target_table).

    Returns ([], None) for statements with no declared target (plain SELECT).
    Returns (sources, target) for CREATE TABLE AS and INSERT INTO SELECT.
    Never raises — parse errors are returned as ([], None).
    """
    if not _SQLGLOT_AVAILABLE:
        return [], None

    try:
        statements = [s for s in sqlglot.parse(sql[:MAX_SQL_LENGTH], read=dialect) if s is not None]
    except Exception:
        return [], None

    for statement in statements:
        target: Any = None
        query: Any = None

        if isinstance(statement, _exp.Create) and isinstance(statement.this, _exp.Table):
            target = statement.this
            query = statement.expression
        elif isinstance(statement, _exp.Insert):
            # INSERT INTO table (...) SELECT ... — this may be a Schema node
            raw_target = statement.this
            if isinstance(raw_target, _exp.Schema):
                raw_target = raw_target.this  # unwrap Schema to the Table
            target = raw_target if isinstance(raw_target, _exp.Table) else None
            query = statement.expression

        if target is None or query is None:
            continue

        target_name = _table_name(target)
        if not target_name:
            continue

        sources = []
        for source_table in sorted(query.find_all(_exp.Table), key=_table_name):
            source_name = _table_name(source_table)
            if source_name and source_name.casefold() != target_name.casefold():
                sources.append(source_name)

        if sources:
            return sources, target_name

    return [], None


def parse_postgres_query_log(
    source: bytes | str | list[dict[str, Any]],
    *,
    filename: str = "query_log.json",
    dialect: str = "postgres",
) -> MetadataGraphResult:
    """Parse a list of PostgreSQL query-log records into POSSIBLE lineage candidates.

    ``source`` may be:
      - A list of dicts, each with at least a ``query`` key (pg_stat_statements shape).
      - A JSON bytes/str encoding such a list, or an object with a ``queries`` key.

    Every emitted relationship has ``evidence_class = "POSSIBLE"`` and carries
    the ``never_proves`` sentence.  Plain SELECT statements produce no relationships.

    Security note: this adapter is opt-in only.  Never call it without an
    explicit user grant for the ``postgres_query_log`` scope.
    """
    if not _SQLGLOT_AVAILABLE:
        return MetadataGraphResult(
            None,
            (Diagnostic(
                "SQLGLOT_NOT_AVAILABLE",
                "The sqlglot library is required for query-log parsing but is not installed. "
                "Install it with: pip install sqlglot",
            ),),
        )

    # ── Load ──────────────────────────────────────────────────────────────
    records: list[dict[str, Any]] = []
    raw_bytes: bytes = b""

    if isinstance(source, list):
        records = source
        try:
            raw_bytes = _canonical_json(source)
        except Exception:
            raw_bytes = json.dumps(source, sort_keys=True).encode("utf-8")

    elif isinstance(source, (bytes, str)):
        raw_bytes = source if isinstance(source, bytes) else source.encode("utf-8")
        if len(raw_bytes) > MAX_FILE_BYTES:
            return MetadataGraphResult(
                None,
                (Diagnostic("FILE_TOO_LARGE",
                    f"File exceeds the {MAX_FILE_BYTES // (1024 * 1024)} MiB limit."),),
            )
        try:
            parsed = json.loads(raw_bytes.decode("utf-8-sig"))
        except (ValueError, UnicodeDecodeError) as exc:
            return MetadataGraphResult(
                None,
                (Diagnostic("INVALID_JSON", f"Could not parse query log JSON: {exc}"),),
            )
        if isinstance(parsed, list):
            records = parsed
        elif isinstance(parsed, dict) and isinstance(parsed.get("queries"), list):
            records = parsed["queries"]
        elif isinstance(parsed, dict) and isinstance(parsed.get("statements"), list):
            records = parsed["statements"]
        else:
            return MetadataGraphResult(
                None,
                (Diagnostic("INVALID_QUERY_LOG",
                    "Query log must be a JSON array of records, or an object with "
                    "a 'queries' or 'statements' array."),),
            )
    else:
        return MetadataGraphResult(
            None,
            (Diagnostic("INVALID_INPUT",
                "Query log source must be a list, bytes, or str."),),
        )

    if not records:
        return MetadataGraphResult(
            None,
            (Diagnostic("EMPTY_QUERY_LOG",
                "The query log contains no records; nothing to ingest."),),
        )

    if len(records) > MAX_QUERY_RECORDS:
        return MetadataGraphResult(
            None,
            (Diagnostic("QUERY_LOG_TOO_LARGE",
                f"Query log contains {len(records)} records; "
                f"the limit is {MAX_QUERY_RECORDS} per import. "
                "Split into smaller batches."),),
        )

    # ── Parse ─────────────────────────────────────────────────────────────
    assets: dict[str, dict[str, Any]] = {}
    relationships: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str]] = set()
    errors: list[Diagnostic] = []
    parse_errors = 0
    skipped_no_target = 0

    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(Diagnostic("INVALID_QUERY_RECORD",
                f"Record at index {index} is not an object.", f"records[{index}]"))
            continue

        sql = record.get("query") or record.get("sql") or record.get("statement") or ""
        if not isinstance(sql, str) or not sql.strip():
            skipped_no_target += 1
            continue

        source_tables, target_table = _extract_tables_from_sql(sql.strip(), dialect=dialect)
        if not target_table:
            skipped_no_target += 1
            continue

        # Build asset id: use qualified name lower-cased
        target_id = "query-log-table:" + target_table.lower()
        assets.setdefault(target_id, {
            "id": target_id,
            "qualified_name": target_table,
            "name": target_table.rsplit(".", 1)[-1],
            "namespace": target_table.rsplit(".", 1)[0] if "." in target_table else "public",
            "type": "TABLE",
            "metadata": {
                "inferred_from": "postgres_query_log",
                "never_proves": NEVER_PROVES,
            },
        })

        for src in source_tables:
            src_id = "query-log-table:" + src.lower()
            assets.setdefault(src_id, {
                "id": src_id,
                "qualified_name": src,
                "name": src.rsplit(".", 1)[-1],
                "namespace": src.rsplit(".", 1)[0] if "." in src else "public",
                "type": "TABLE",
                "metadata": {
                    "inferred_from": "postgres_query_log",
                    "never_proves": NEVER_PROVES,
                },
            })

            edge_key = (src_id, target_id)
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                relationships.append({
                    "source_id": src_id,
                    "target_id": target_id,
                    "edge_type": "sql_static_candidate",
                    "evidence_class": "POSSIBLE",
                    "provenance": (
                        "Inferred from PostgreSQL query log. "
                        "This is POSSIBLE evidence only — "
                        + NEVER_PROVES
                    ),
                })

    if errors:
        return MetadataGraphResult(None, tuple(errors))

    if not assets:
        return MetadataGraphResult(
            None,
            (Diagnostic("NO_LINEAGE_CANDIDATES",
                "No lineage candidates could be extracted. "
                f"Processed {len(records)} record(s); "
                f"{skipped_no_target} had no declared target (plain SELECT or unrecognised)."),),
        )

    # ── Build envelope ────────────────────────────────────────────────────
    content_sha256 = hashlib.sha256(raw_bytes).hexdigest()

    envelope: dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "source": {
            "kind": "postgres_query_log",
            "ref": filename,
        },
        "assets": list(assets.values()),
        "relationships": relationships,
        "runs": [],
        "evidence": [],
        "diagnostics": [],
        "provenance": {
            "adapter": "kairos.postgres_query_log",
            "adapter_version": ADAPTER_VERSION,
            "original_filename": filename,
            "content_sha256": content_sha256,
            "never_proves": NEVER_PROVES,
            "scope_requirement": (
                "opt-in only: the workspace owner must explicitly grant the "
                "'postgres_query_log' scope before this adapter may be used."
            ),
            "evidence_class": "POSSIBLE",
            "records_processed": len(records),
            "records_with_target": len(relationships),
            "records_skipped_no_target": skipped_no_target,
        },
    }

    warnings: list[Diagnostic] = []
    if skipped_no_target > 0:
        warnings.append(Diagnostic(
            "QUERIES_WITHOUT_LINEAGE_TARGET",
            f"{skipped_no_target} query record(s) had no declared target "
            "(plain SELECT, unsupported syntax, or missing query text). "
            "These produced no lineage candidates.",
        ))

    return MetadataGraphResult(envelope, (), tuple(warnings))
