"""
Olist CSV Loader for KAIROS — Fast batch insert version
Loads first 500 rows per table into raw_event in Supabase.
Run: python scripts/load_olist_csvs.py
"""

import sys
import csv
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.app.db import get_cursor

NOW = datetime.now(timezone.utc).isoformat()
OLIST_DIR = Path("E:/EDI-Metadata_Lineage/Olist dataset")
MAX_ROWS = 100  # Keep fast and within Supabase free tier

CSV_TABLE_MAP = {
    "olist_customers_dataset.csv":           "olist_customers",
    "olist_orders_dataset.csv":              "olist_orders",
    "olist_order_items_dataset.csv":         "olist_order_items",
    "olist_order_payments_dataset.csv":      "olist_order_payments",
    "olist_order_reviews_dataset.csv":       "olist_order_reviews",
    "olist_products_dataset.csv":            "olist_products",
    "olist_sellers_dataset.csv":             "olist_sellers",
    "product_category_name_translation.csv": "olist_product_category_translation",
    # Skip geolocation — too large (1M+ rows)
}


def load_csv_batch(cur, csv_path: Path, table_name: str):
    """Batch insert CSV rows into raw_event."""
    rows_to_insert = []

    with open(csv_path, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= MAX_ROWS:
                break
            payload = dict(row)
            payload["_table"] = table_name
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            ph = hashlib.sha256(canonical.encode()).hexdigest()
            event_id = f"olist:{table_name}:{ph[:20]}"
            rows_to_insert.append((event_id, json.dumps(payload), ph, "olist"))

    if not rows_to_insert:
        print(f"  SKIP: {csv_path.name} — no rows")
        return 0

    # Batch insert using executemany
    cur.executemany("""
        INSERT INTO raw_event (event_id, payload, payload_hash, source_system, ingestion_time)
        VALUES (%s, %s, %s, %s, NOW())
        ON CONFLICT (event_id) DO NOTHING
    """, rows_to_insert)

    print(f"  ✅ {csv_path.name} → {len(rows_to_insert)} rows → {table_name}")
    return len(rows_to_insert)


if __name__ == "__main__":
    print("=" * 50)
    print("KAIROS — Loading Olist CSVs (batch mode)")
    print(f"Max {MAX_ROWS} rows per table")
    print("=" * 50)

    total = 0
    with get_cursor() as cur:
        for csv_file, table_name in CSV_TABLE_MAP.items():
            csv_path = OLIST_DIR / csv_file
            if csv_path.exists():
                total += load_csv_batch(cur, csv_path, table_name)
            else:
                print(f"  SKIP: {csv_file} not found")

        # Verify
        cur.execute("SELECT COUNT(*) as cnt FROM raw_event WHERE source_system = 'olist'")
        print(f"\n  Total Olist raw events in Supabase: {cur.fetchone()['cnt']}")

    print(f"\n✅ Done! {total} rows loaded into Supabase")
