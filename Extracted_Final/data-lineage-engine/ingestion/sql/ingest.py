"""
M1: SQL Lineage Ingestion Pipeline
====================================
SQLGlot output → column_record creation → evidence storage in Supabase

Flow:
    SQL text + SchemaSnapshot
        ↓
    SQLGlotLineageProvider.extract()
        ↓
    StaticEvidence objects
        ↓
    ingest_static_evidence()
        ↓
    Supabase:
        dataset        (ensure source/target datasets exist)
        column_record  (ensure source/target columns exist)
        evidence       (store STATIC_DEPENDENCY records)

IMPORTANT:
- evidence_type = 'STATIC_DEPENDENCY'  (not RUNTIME_POSITIVE — that is M2's job)
- source_column_id / target_column_id are UUID references to column_record
- column_record must be created BEFORE evidence can reference it
- Idempotent: ON CONFLICT DO NOTHING everywhere
"""

from __future__ import annotations

import hashlib
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence

# Allow running as a script from repo root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.app.db import get_cursor
from contracts.evidence import StaticEvidence
from contracts.interfaces import SchemaSnapshot, StaticExtraction
from contracts.types import Granularity, ParserStatus
from ingestion.sql import SQLGlotLineageProvider

NOW = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _dataset_id(source_system: str, schema_name: str, table_name: str) -> str:
    """Deterministic UUID for a dataset — matches seed_supabase.py."""
    key = f"{source_system}.{schema_name}.{table_name}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, key))


def _column_id(dataset_id: str, column_name: str, schema_version: str = "v1") -> str:
    """Deterministic UUID for a column record."""
    key = f"{dataset_id}.{schema_version}.{column_name}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, key))


# ---------------------------------------------------------------------------
# Step 1: Ensure dataset exists in Supabase
# ---------------------------------------------------------------------------

def ensure_dataset(
    cur,
    source_system: str,
    namespace: str,
    database_name: str,
    schema_name: str,
    table_name: str,
    asset_type: str = "TABLE",
) -> str:
    """Insert dataset if not exists. Returns dataset UUID."""
    ds_id = _dataset_id(source_system, schema_name, table_name)
    cur.execute("""
        INSERT INTO dataset (id, source_system, namespace, database_name,
                             schema_name, name, asset_type)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_system, namespace, database_name, schema_name, name, asset_type)
        DO NOTHING
    """, (ds_id, source_system, namespace, database_name, schema_name, table_name, asset_type))
    return ds_id


# ---------------------------------------------------------------------------
# Step 2: Ensure column_record exists in Supabase
# ---------------------------------------------------------------------------

def ensure_column_record(
    cur,
    dataset_id: str,
    column_name: str,
    data_type: str = "TEXT",
    schema_version: str = "v1",
) -> str:
    """Insert column_record if not exists. Returns column UUID."""
    col_id = _column_id(dataset_id, column_name, schema_version)
    cur.execute("""
        INSERT INTO column_record (id, dataset_id, column_name, data_type, schema_version)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (dataset_id, schema_version, column_name)
        DO NOTHING
    """, (col_id, dataset_id, column_name, data_type, schema_version))
    return col_id


# ---------------------------------------------------------------------------
# Step 3: Store StaticEvidence in Supabase evidence table
# ---------------------------------------------------------------------------

def store_static_evidence(
    cur,
    ev: StaticEvidence,
    source_column_uuid: Optional[str],
    target_column_uuid: Optional[str],
    source_dataset_uuid: str,
    target_dataset_uuid: str,
) -> None:
    """
    Insert one StaticEvidence record into the evidence table.
    evidence_type = 'STATIC_DEPENDENCY' (EvidenceType.STATIC_DEPENDENCY)
    Never stores absence — only positive dependency edges.
    """
    if ev.parser_status == ParserStatus.UNSUPPORTED:
        # Architecture rule: unsupported SQL → engine produces UNKNOWN
        # We store a diagnostics-only record so M5 can show the reason
        cur.execute("""
            INSERT INTO evidence (
                evidence_id, evidence_type, source_system,
                source_dataset_id, target_dataset_id,
                granularity, operator, query_fingerprint,
                schema_fingerprint, expression_fingerprint,
                parser_status, diagnostics, ingestion_time
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (evidence_id) DO NOTHING
        """, (
            ev.evidence_id,
            "STATIC_DEPENDENCY",
            "sqlglot",
            source_dataset_uuid,
            target_dataset_uuid,
            ev.granularity.value,
            ev.operator,
            ev.query_fingerprint,
            ev.schema_fingerprint,
            ev.expression_fingerprint,
            ev.parser_status.value,
            str(list(ev.diagnostics)) if ev.diagnostics else None,
        ))
        return

    # Positive dependency — store full record with column UUIDs
    cur.execute("""
        INSERT INTO evidence (
            evidence_id, evidence_type, source_system,
            source_dataset_id, target_dataset_id,
            source_column_id, target_column_id,
            granularity, operator,
            query_fingerprint, schema_fingerprint, expression_fingerprint,
            parser_status, ingestion_time
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (evidence_id) DO NOTHING
    """, (
        ev.evidence_id,
        "STATIC_DEPENDENCY",
        "sqlglot",
        source_dataset_uuid,
        target_dataset_uuid,
        source_column_uuid,
        target_column_uuid,
        ev.granularity.value,
        ev.operator,
        ev.query_fingerprint,
        ev.schema_fingerprint,
        ev.expression_fingerprint,
        ev.parser_status.value,
    ))


# ---------------------------------------------------------------------------
# Step 4: Store lineage edge + temporal version
# ---------------------------------------------------------------------------

def ensure_lineage_edge(
    cur,
    source_id: str,
    target_id: str,
    granularity: str,
    query_fingerprint: str,
    operator_fingerprint: str,
    evidence_uuid: Optional[str] = None,
) -> str:
    """Insert lineage edge + temporal version. Returns edge UUID."""
    edge_id = str(uuid.uuid5(
        uuid.NAMESPACE_DNS,
        f"edge:{source_id}:{target_id}:{granularity}:{query_fingerprint}"
    ))
    cur.execute("""
        INSERT INTO lineage_edge (id, source_id, target_id, granularity,
                                  operator_fingerprint, query_fingerprint)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
    """, (edge_id, source_id, target_id, granularity, operator_fingerprint, query_fingerprint))

    # Temporal version — open-ended, valid from ingestion time
    ver_id = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO edge_temporal_version (
            version_id, edge_id, valid_from, valid_to,
            effective_time_status, transaction_from, transaction_to,
            source_system, evidence_id
        )
        SELECT %s, %s, %s, NULL, 'KNOWN', %s, NULL, %s, ev.id
        FROM (SELECT id FROM evidence WHERE evidence_id = %s LIMIT 1) ev
        ON CONFLICT DO NOTHING
    """, (ver_id, edge_id, NOW, NOW, "sqlglot",
          evidence_uuid if evidence_uuid else ""))

    # Fallback if evidence not stored yet
    cur.execute("""
        INSERT INTO edge_temporal_version (
            version_id, edge_id, valid_from, valid_to,
            effective_time_status, transaction_from, transaction_to,
            source_system
        )
        SELECT %s, %s, %s, NULL, 'KNOWN', %s, NULL, %s
        WHERE NOT EXISTS (
            SELECT 1 FROM edge_temporal_version WHERE version_id = %s
        )
    """, (ver_id, edge_id, NOW, NOW, "sqlglot", ver_id))

    return edge_id


# ---------------------------------------------------------------------------
# Main public API
# ---------------------------------------------------------------------------

def ingest_static_evidence(
    extraction: StaticExtraction,
    schema: SchemaSnapshot,
    source_system: str = "sqlglot",
    namespace: str = "kairos",
    database_name: str = "kairos",
) -> dict:
    """
    Store all StaticEvidence from a SQLGlot extraction into Supabase.

    Steps per evidence record:
    1. Ensure source dataset exists (dataset table)
    2. Ensure target dataset exists (dataset table)
    3. Ensure source column exists (column_record table)
    4. Ensure target column exists (column_record table)
    5. Store evidence (evidence table) — type = STATIC_DEPENDENCY
    6. Store lineage edge + temporal version

    Returns summary dict with counts.
    """
    stored = 0
    skipped_unsupported = 0
    errors = []

    with get_cursor() as cur:
        for ev in extraction.evidence:
            try:
                # --- Parse column IDs from evidence ---
                # source_column_id format: "dataset.column" or just "column"
                src_col_uuid = None
                tgt_col_uuid = None
                src_ds_uuid = None
                tgt_ds_uuid = None

                # Determine source dataset and column
                if ev.source_column_id and "." in ev.source_column_id:
                    parts = ev.source_column_id.split(".", 1)
                    src_table = parts[0]
                    src_col_name = parts[1]
                else:
                    src_table = ev.source_dataset_id
                    src_col_name = ev.source_column_id

                # Determine target dataset and column
                if ev.target_column_id and "." in ev.target_column_id:
                    parts = ev.target_column_id.split(".", 1)
                    tgt_table = parts[0]
                    tgt_col_name = parts[1]
                else:
                    tgt_table = ev.target_dataset_id
                    tgt_col_name = ev.target_column_id

                # Infer schema from SchemaSnapshot
                schema_name = schema.dataset_id.split(".")[-1] if "." in schema.dataset_id else schema.dataset_id

                # Step 1+2: Ensure datasets exist
                src_ds_uuid = ensure_dataset(
                    cur, source_system, namespace, database_name,
                    schema_name, src_table or schema_name
                )
                tgt_ds_uuid = ensure_dataset(
                    cur, source_system, namespace, database_name,
                    schema_name, tgt_table or schema_name
                )

                # Step 3+4: Ensure columns exist (only for COLUMN granularity)
                if ev.granularity == Granularity.COLUMN and src_col_name:
                    src_col_uuid = ensure_column_record(
                        cur, src_ds_uuid, src_col_name
                    )
                if ev.granularity == Granularity.COLUMN and tgt_col_name:
                    tgt_col_uuid = ensure_column_record(
                        cur, tgt_ds_uuid, tgt_col_name
                    )

                # Step 5: Store evidence
                store_static_evidence(
                    cur, ev,
                    src_col_uuid, tgt_col_uuid,
                    src_ds_uuid, tgt_ds_uuid,
                )

                # Step 6: Store lineage edge
                if ev.parser_status != ParserStatus.UNSUPPORTED:
                    source_id = src_col_uuid or src_ds_uuid
                    target_id = tgt_col_uuid or tgt_ds_uuid
                    if source_id and target_id:
                        ensure_lineage_edge(
                            cur,
                            source_id=source_id,
                            target_id=target_id,
                            granularity=ev.granularity.value,
                            query_fingerprint=ev.query_fingerprint,
                            operator_fingerprint=hashlib.sha256(
                                ev.operator.encode()
                            ).hexdigest()[:16],
                            evidence_uuid=ev.evidence_id,
                        )
                    stored += 1
                else:
                    skipped_unsupported += 1

            except Exception as e:
                errors.append(f"{ev.evidence_id}: {e}")

    return {
        "stored": stored,
        "skipped_unsupported": skipped_unsupported,
        "errors": errors,
        "total": len(extraction.evidence),
    }


# ---------------------------------------------------------------------------
# Convenience: run all corpus cases through the pipeline
# ---------------------------------------------------------------------------

def ingest_corpus(corpus_dir: Optional[Path] = None) -> dict:
    """
    Run all M1 corpus SQL cases through SQLGlot and store in Supabase.
    This is the main entry point for the M1 → DB pipeline.
    """
    import json

    if corpus_dir is None:
        corpus_dir = Path(__file__).parent / "corpus"

    provider = SQLGlotLineageProvider()
    total_stored = 0
    total_skipped = 0
    all_errors = []
    cases_processed = 0

    for case_file in sorted(corpus_dir.glob("W*.json")):
        case = json.loads(case_file.read_text(encoding="utf-8"))
        case_id = case["case_id"]
        sql = case["sql"]
        dialect = case.get("dialect", "postgres")

        # Build SchemaSnapshot from corpus case
        schema_data = case.get("schema", {})
        if not schema_data:
            print(f"  SKIP {case_id}: no schema defined")
            continue

        # Use first table as dataset_id
        first_table = list(schema_data.keys())[0]
        all_columns = []
        for table_name, cols in schema_data.items():
            for col_name in cols.keys():
                all_columns.append(f"{table_name}.{col_name}")

        schema = SchemaSnapshot(
            dataset_id=first_table,
            columns=tuple(all_columns),
            fingerprint=hashlib.sha256(
                json.dumps(schema_data, sort_keys=True).encode()
            ).hexdigest()[:16],
        )

        # Extract lineage
        extraction = provider.extract(sql, schema, dialect=dialect)

        # Ingest into Supabase
        result = ingest_static_evidence(extraction, schema)
        total_stored += result["stored"]
        total_skipped += result["skipped_unsupported"]
        all_errors.extend(result["errors"])
        cases_processed += 1

        status = "OK" if not result["errors"] else "WARN"
        print(f"  {status} {case_id}: "
              f"{result['stored']} stored, "
              f"{result['skipped_unsupported']} unsupported")

    return {
        "cases_processed": cases_processed,
        "total_stored": total_stored,
        "total_skipped": total_skipped,
        "errors": all_errors,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 55)
    print("M1: SQL Lineage Ingestion -- SQLGlot to Supabase")
    print("=" * 55)

    print("\nRunning corpus cases through SQLGlot and storing in DB...")
    result = ingest_corpus()

    print(f"\n{'=' * 55}")
    print(f"Cases processed : {result['cases_processed']}")
    print(f"Evidence stored : {result['total_stored']}")
    print(f"Unsupported     : {result['total_skipped']}")
    if result["errors"]:
        print(f"Errors          : {len(result['errors'])}")
        for e in result["errors"]:
            print(f"  ERROR: {e}")
    else:
        print("Errors          : 0")

    print("\nVerifying Supabase...")
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) as cnt FROM column_record")
        print(f"  column_record rows : {cur.fetchone()['cnt']}")
        cur.execute("SELECT COUNT(*) as cnt FROM evidence WHERE evidence_type = 'STATIC_DEPENDENCY'")
        print(f"  STATIC_DEPENDENCY  : {cur.fetchone()['cnt']}")
        cur.execute("SELECT COUNT(*) as cnt FROM lineage_edge")
        print(f"  lineage_edge rows  : {cur.fetchone()['cnt']}")

    print("\n✓ M1 ingestion pipeline complete!")
