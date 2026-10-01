"""Verify all data in Supabase after seeding."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.app.db import get_cursor

with get_cursor() as cur:
    print("=== SUPABASE COMPLETE SUMMARY ===\n")

    # Total datasets
    cur.execute("SELECT COUNT(*) as cnt FROM dataset")
    print(f"Total datasets: {cur.fetchone()['cnt']}")

    # By source system
    cur.execute("SELECT source_system, COUNT(*) as cnt FROM dataset GROUP BY source_system ORDER BY source_system")
    for r in cur.fetchall():
        print(f"  [{r['source_system']}]: {r['cnt']} tables")

    print()

    # Lineage edges
    cur.execute("SELECT COUNT(*) as cnt FROM lineage_edge")
    print(f"Total lineage edges: {cur.fetchone()['cnt']}")

    cur.execute("SELECT COUNT(*) as cnt FROM edge_temporal_version")
    print(f"Total temporal versions: {cur.fetchone()['cnt']}")

    print()

    # Raw events
    cur.execute("SELECT source_system, COUNT(*) as cnt FROM raw_event GROUP BY source_system")
    for r in cur.fetchall():
        print(f"Raw events [{r['source_system']}]: {r['cnt']}")

    print()

    # Evidence
    cur.execute("SELECT COUNT(*) as cnt FROM evidence")
    print(f"Total evidence records: {cur.fetchone()['cnt']}")

    print()
    print("=== OLIST TABLES ===")
    cur.execute("""
        SELECT schema_name, name
        FROM dataset
        WHERE source_system = 'olist'
        ORDER BY schema_name, name
    """)
    for r in cur.fetchall():
        print(f"  {r['schema_name']}.{r['name']}")

    print()
    print("=== OLIST RAW EVENT SAMPLE ===")
    cur.execute("""
        SELECT event_id, payload->>'_table' as tbl
        FROM raw_event
        WHERE source_system = 'olist'
        GROUP BY event_id, tbl
        LIMIT 5
    """)
    for r in cur.fetchall():
        print(f"  {r['tbl']}: {r['event_id'][:40]}...")

    print()
    print("=== LINEAGE EDGES SAMPLE ===")
    cur.execute("""
        SELECT src.name as source, tgt.name as target
        FROM lineage_edge le
        JOIN dataset src ON src.id = le.source_id
        JOIN dataset tgt ON tgt.id = le.target_id
        WHERE src.source_system = 'olist'
        ORDER BY src.name, tgt.name
        LIMIT 10
    """)
    for r in cur.fetchall():
        print(f"  {r['source']} -> {r['target']}")
