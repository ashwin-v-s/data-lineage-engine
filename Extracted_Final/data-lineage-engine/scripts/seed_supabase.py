"""
Seed Supabase with sample KAIROS data.
Loads datasets, lineage edges and evidence from M1 corpus.
Run once: python scripts/seed_supabase.py
"""

import sys
import os
import uuid
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.db import get_cursor

NOW = datetime.now(timezone.utc).isoformat()

# ---------------------------------------------------------------------------
# Sample datasets (these become nodes in the UI)
# ---------------------------------------------------------------------------
DATASETS = [
    {
        "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "kairos.raw.orders")),
        "source_system": "postgres",
        "namespace": "kairos",
        "database_name": "kairos",
        "schema_name": "raw",
        "name": "orders",
        "asset_type": "TABLE",
    },
    {
        "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "kairos.raw.employees")),
        "source_system": "postgres",
        "namespace": "kairos",
        "database_name": "kairos",
        "schema_name": "raw",
        "name": "employees",
        "asset_type": "TABLE",
    },
    {
        "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "kairos.raw.customers")),
        "source_system": "postgres",
        "namespace": "kairos",
        "database_name": "kairos",
        "schema_name": "raw",
        "name": "customers",
        "asset_type": "TABLE",
    },
    {
        "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "kairos.staging.stg_customer_orders")),
        "source_system": "postgres",
        "namespace": "kairos",
        "database_name": "kairos",
        "schema_name": "staging",
        "name": "stg_customer_orders",
        "asset_type": "TABLE",
    },
    {
        "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "kairos.warehouse.orders_fact")),
        "source_system": "postgres",
        "namespace": "kairos",
        "database_name": "kairos",
        "schema_name": "warehouse",
        "name": "orders_fact",
        "asset_type": "TABLE",
    },
    {
        "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "kairos.warehouse.customers_dim")),
        "source_system": "postgres",
        "namespace": "kairos",
        "database_name": "kairos",
        "schema_name": "warehouse",
        "name": "customers_dim",
        "asset_type": "TABLE",
    },
    {
        "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "kairos.mart.revenue_summary")),
        "source_system": "postgres",
        "namespace": "kairos",
        "database_name": "kairos",
        "schema_name": "mart",
        "name": "revenue_summary",
        "asset_type": "TABLE",
    },
]

# ---------------------------------------------------------------------------
# Sample jobs and runs
# ---------------------------------------------------------------------------
JOB_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, "kairos.etl_pipeline"))
RUN_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, "kairos.run_2026_09_23"))

# ---------------------------------------------------------------------------
# Sample lineage edges (source → target)
# ---------------------------------------------------------------------------
def make_edge(src_name, tgt_name, operator="DERIVED_FROM"):
    src_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"kairos.{src_name}"))
    tgt_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"kairos.{tgt_name}"))
    edge_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{src_id}->{tgt_id}"))
    return {
        "id": edge_id,
        "source_dataset_id": src_id,
        "target_dataset_id": tgt_id,
        "granularity": "DATASET",
        "operator_fingerprint": hashlib.sha256(operator.encode()).hexdigest()[:16],
        "query_fingerprint": hashlib.sha256(f"{src_name}->{tgt_name}".encode()).hexdigest()[:16],
    }

EDGES = [
    make_edge("raw.orders",                "staging.stg_customer_orders"),
    make_edge("raw.customers",             "staging.stg_customer_orders"),
    make_edge("staging.stg_customer_orders", "warehouse.orders_fact"),
    make_edge("warehouse.customers_dim",   "warehouse.orders_fact"),
    make_edge("warehouse.orders_fact",     "mart.revenue_summary"),
]

# ---------------------------------------------------------------------------
# Sample evidence (from M1 SQLGlot corpus)
# ---------------------------------------------------------------------------
CORPUS_DIR = Path(__file__).parent.parent / "ingestion" / "sql" / "corpus"

def load_corpus_evidence():
    """Load static evidence from M1 corpus JSON files."""
    evidence_list = []
    for f in CORPUS_DIR.glob("W*.json"):
        case = json.loads(f.read_text())
        if not case.get("expected"):
            continue
        sql = case["sql"]
        qfp = hashlib.sha256(sql.encode()).hexdigest()[:16]
        for tgt_col, src_cols in case["expected"].items():
            for src_col in src_cols:
                ev_id = hashlib.sha256(f"{qfp}:{src_col}->{tgt_col}".encode()).hexdigest()[:32]
                evidence_list.append({
                    "id": ev_id,
                    "evidence_type": "STATIC_DEPENDENCY",
                    "source_system": "sqlglot",
                    "run_id": None,
                    "source_column_id": src_col,
                    "target_column_id": tgt_col,
                    "granularity": "COLUMN",
                    "operator": "project",
                    "query_fingerprint": qfp,
                    "schema_fingerprint": "schema-v1",
                    "expression_fingerprint": hashlib.sha256(src_col.encode()).hexdigest()[:8],
                    "parser_status": "SUPPORTED",
                    "payload_reference": case["case_id"],
                    "raw_payload_hash": hashlib.sha256(json.dumps(case).encode()).hexdigest(),
                })
    return evidence_list


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------
def seed_datasets(cur):
    print("Seeding datasets...")
    count = 0
    for ds in DATASETS:
        cur.execute("""
            INSERT INTO dataset (id, source_system, namespace, database_name, schema_name, name, asset_type)
            VALUES (%(id)s, %(source_system)s, %(namespace)s, %(database_name)s,
                    %(schema_name)s, %(name)s, %(asset_type)s)
            ON CONFLICT (source_system, namespace, database_name, schema_name, name, asset_type)
            DO NOTHING
        """, ds)
        count += 1
    print(f"  ✅ {count} datasets inserted")


def seed_jobs_and_runs(cur):
    print("Seeding jobs and runs...")
    cur.execute("""
        INSERT INTO job (id, namespace, name)
        VALUES (%s, %s, %s)
        ON CONFLICT DO NOTHING
    """, (JOB_ID, "kairos", "etl_pipeline"))

    cur.execute("""
        INSERT INTO execution_run (id, run_id, job_id, started_at, status)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
    """, (RUN_ID, "run_2026_09_23_093214", JOB_ID, NOW, "completed"))
    print("  ✅ 1 job + 1 run inserted")


def seed_lineage_edges(cur):
    print("Seeding lineage edges...")
    count = 0
    for edge in EDGES:
        # Insert logical edge (uses source_id/target_id not source_dataset_id)
        cur.execute("""
            INSERT INTO lineage_edge (id, source_id, target_id,
                granularity, operator_fingerprint, query_fingerprint)
            VALUES (%(id)s, %(source_dataset_id)s, %(target_dataset_id)s,
                    %(granularity)s, %(operator_fingerprint)s, %(query_fingerprint)s)
            ON CONFLICT DO NOTHING
        """, edge)

        # Insert temporal version
        ver_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO edge_temporal_version (
                version_id, edge_id, valid_from, valid_to,
                effective_time_status, transaction_from, transaction_to,
                source_system
            )
            VALUES (%s, %s, %s, NULL, %s, %s, NULL, %s)
            ON CONFLICT DO NOTHING
        """, (ver_id, edge["id"], "2026-01-01T00:00:00Z", "KNOWN", NOW, "kairos_seed"))
        count += 1
    print(f"  ✅ {count} lineage edges + temporal versions inserted")


def seed_evidence(cur):
    print("Seeding static evidence from M1 corpus...")
    evidence_list = load_corpus_evidence()
    count = 0
    for ev in evidence_list:
        cur.execute("""
            INSERT INTO evidence (
                evidence_id, evidence_type, source_system, run_id,
                source_column_id, target_column_id, granularity,
                operator, query_fingerprint, schema_fingerprint,
                expression_fingerprint, parser_status,
                ingestion_time
            )
            VALUES (
                %(id)s, %(evidence_type)s, %(source_system)s, %(run_id)s,
                NULL, NULL, %(granularity)s,
                %(operator)s, %(query_fingerprint)s, %(schema_fingerprint)s,
                %(expression_fingerprint)s, %(parser_status)s,
                NOW()
            )
            ON CONFLICT DO NOTHING
        """, ev)
        count += 1
    print(f"  ✅ {count} static evidence records inserted from M1 corpus")


def verify(cur):
    print("\nVerifying Supabase data...")
    for table in ["dataset", "job", "execution_run", "lineage_edge",
                  "edge_temporal_version", "evidence"]:
        cur.execute(f"SELECT COUNT(*) as cnt FROM {table}")
        row = cur.fetchone()
        print(f"  {table}: {row['cnt']} rows")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 50)
    print("KAIROS — Seeding Supabase")
    print("=" * 50)

    with get_cursor() as cur:
        seed_datasets(cur)
        seed_jobs_and_runs(cur)
        seed_lineage_edges(cur)
        seed_evidence(cur)
        verify(cur)

    print("\n✅ Supabase seeding complete!")
    print("Run the backend and open http://localhost:3000 to see real data.")
