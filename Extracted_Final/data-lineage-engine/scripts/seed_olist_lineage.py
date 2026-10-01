"""
Olist Dataset — Lineage Seeder for KAIROS

Seeds the 9 Olist tables as datasets in Supabase,
and their known lineage relationships as edges.

Olist dataset: Brazilian E-Commerce Public Dataset
License: CC BY-NC-SA 4.0
Source: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

9 CSV files:
- olist_customers_dataset.csv
- olist_geolocation_dataset.csv
- olist_order_items_dataset.csv
- olist_order_payments_dataset.csv
- olist_order_reviews_dataset.csv
- olist_orders_dataset.csv
- olist_products_dataset.csv
- olist_sellers_dataset.csv
- olist_product_category_name_translation.csv

Run: python scripts/seed_olist_lineage.py
"""

import sys
import os
import uuid
import hashlib
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.app.db import get_cursor

NOW = datetime.now(timezone.utc).isoformat()

# ---------------------------------------------------------------------------
# Olist 9 tables — these become nodes in the lineage graph
# ---------------------------------------------------------------------------
OLIST_TABLES = [
    {
        "name": "olist_orders",
        "schema_name": "olist",
        "description": "Core orders table — 100k orders 2016-2018",
        "columns": ["order_id", "customer_id", "order_status", "order_purchase_timestamp",
                    "order_approved_at", "order_delivered_carrier_date",
                    "order_delivered_customer_date", "order_estimated_delivery_date"],
    },
    {
        "name": "olist_customers",
        "schema_name": "olist",
        "description": "Customer data with location info",
        "columns": ["customer_id", "customer_unique_id", "customer_zip_code_prefix",
                    "customer_city", "customer_state"],
    },
    {
        "name": "olist_order_items",
        "schema_name": "olist",
        "description": "Items within each order",
        "columns": ["order_id", "order_item_id", "product_id", "seller_id",
                    "shipping_limit_date", "price", "freight_value"],
    },
    {
        "name": "olist_order_payments",
        "schema_name": "olist",
        "description": "Payment methods and values per order",
        "columns": ["order_id", "payment_sequential", "payment_type",
                    "payment_installments", "payment_value"],
    },
    {
        "name": "olist_order_reviews",
        "schema_name": "olist",
        "description": "Customer reviews and scores per order",
        "columns": ["review_id", "order_id", "review_score", "review_comment_title",
                    "review_comment_message", "review_creation_date", "review_answer_timestamp"],
    },
    {
        "name": "olist_products",
        "schema_name": "olist",
        "description": "Product catalog with dimensions and weight",
        "columns": ["product_id", "product_category_name", "product_name_length",
                    "product_description_length", "product_photos_qty",
                    "product_weight_g", "product_length_cm", "product_height_cm",
                    "product_width_cm"],
    },
    {
        "name": "olist_sellers",
        "schema_name": "olist",
        "description": "Seller data with location info",
        "columns": ["seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"],
    },
    {
        "name": "olist_geolocation",
        "schema_name": "olist",
        "description": "ZIP code to latitude/longitude mapping",
        "columns": ["geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng",
                    "geolocation_city", "geolocation_state"],
    },
    {
        "name": "olist_product_category_translation",
        "schema_name": "olist",
        "description": "Product category name in Portuguese and English",
        "columns": ["product_category_name", "product_category_name_english"],
    },
    # Derived/analytics tables
    {
        "name": "olist_orders_enriched",
        "schema_name": "olist_analytics",
        "description": "Orders joined with customers, payments and items",
        "columns": ["order_id", "customer_id", "customer_state", "order_status",
                    "total_payment_value", "item_count", "avg_freight_value"],
    },
    {
        "name": "olist_revenue_by_category",
        "schema_name": "olist_analytics",
        "description": "Revenue aggregated by product category",
        "columns": ["product_category_name_english", "total_revenue",
                    "order_count", "avg_review_score"],
    },
    {
        "name": "olist_seller_performance",
        "schema_name": "olist_analytics",
        "description": "Seller performance metrics",
        "columns": ["seller_id", "seller_state", "total_orders", "avg_delivery_days",
                    "avg_review_score", "total_revenue"],
    },
]

# ---------------------------------------------------------------------------
# Olist lineage relationships
# These are the SQL-derived lineage edges between Olist tables
# ---------------------------------------------------------------------------
OLIST_LINEAGE = [
    # Core joins: orders is the central hub
    ("olist.olist_orders",       "olist.olist_order_items",    "JOIN on order_id"),
    ("olist.olist_orders",       "olist.olist_order_payments", "JOIN on order_id"),
    ("olist.olist_orders",       "olist.olist_order_reviews",  "JOIN on order_id"),
    ("olist.olist_orders",       "olist.olist_customers",      "JOIN on customer_id"),

    # Items join to products and sellers
    ("olist.olist_order_items",  "olist.olist_products",       "JOIN on product_id"),
    ("olist.olist_order_items",  "olist.olist_sellers",        "JOIN on seller_id"),

    # Translation join
    ("olist.olist_products",     "olist.olist_product_category_translation",
     "JOIN on product_category_name"),

    # Geolocation enrichment
    ("olist.olist_customers",    "olist.olist_geolocation",    "JOIN on zip_code_prefix"),
    ("olist.olist_sellers",      "olist.olist_geolocation",    "JOIN on zip_code_prefix"),

    # Analytics derived tables
    ("olist.olist_orders",            "olist_analytics.olist_orders_enriched",     "CTAS/ETL"),
    ("olist.olist_customers",         "olist_analytics.olist_orders_enriched",     "CTAS/ETL"),
    ("olist.olist_order_payments",    "olist_analytics.olist_orders_enriched",     "CTAS/ETL"),
    ("olist.olist_order_items",       "olist_analytics.olist_orders_enriched",     "CTAS/ETL"),

    ("olist.olist_order_items",       "olist_analytics.olist_revenue_by_category", "CTAS/ETL"),
    ("olist.olist_products",          "olist_analytics.olist_revenue_by_category", "CTAS/ETL"),
    ("olist.olist_product_category_translation",
     "olist_analytics.olist_revenue_by_category", "CTAS/ETL"),
    ("olist.olist_order_reviews",     "olist_analytics.olist_revenue_by_category", "CTAS/ETL"),

    ("olist.olist_sellers",           "olist_analytics.olist_seller_performance",  "CTAS/ETL"),
    ("olist.olist_order_items",       "olist_analytics.olist_seller_performance",  "CTAS/ETL"),
    ("olist.olist_orders",            "olist_analytics.olist_seller_performance",  "CTAS/ETL"),
    ("olist.olist_order_reviews",     "olist_analytics.olist_seller_performance",  "CTAS/ETL"),
]


def make_dataset_id(schema, name):
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"olist.{schema}.{name}"))


def seed_olist_datasets(cur):
    print("Seeding Olist datasets...")
    count = 0
    for tbl in OLIST_TABLES:
        ds_id = make_dataset_id(tbl["schema_name"], tbl["name"])
        cur.execute("""
            INSERT INTO dataset (id, source_system, namespace, database_name,
                                 schema_name, name, asset_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_system, namespace, database_name,
                         schema_name, name, asset_type)
            DO NOTHING
        """, (ds_id, "olist", "kairos", "olist_ecommerce",
              tbl["schema_name"], tbl["name"], "TABLE"))
        count += 1
    print(f"  ✅ {count} Olist datasets inserted")


def seed_olist_edges(cur):
    print("Seeding Olist lineage edges...")
    count = 0
    for src_full, tgt_full, operator in OLIST_LINEAGE:
        # Parse schema.name
        src_schema, src_name = src_full.split(".", 1)
        tgt_schema, tgt_name = tgt_full.split(".", 1)

        src_id = make_dataset_id(src_schema, src_name)
        tgt_id = make_dataset_id(tgt_schema, tgt_name)
        edge_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"olist.{src_id}->{tgt_id}"))
        op_fp = hashlib.sha256(operator.encode()).hexdigest()[:16]
        q_fp = hashlib.sha256(f"{src_full}->{tgt_full}".encode()).hexdigest()[:16]

        cur.execute("""
            INSERT INTO lineage_edge (id, source_id, target_id,
                granularity, operator_fingerprint, query_fingerprint)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (edge_id, src_id, tgt_id, "DATASET", op_fp, q_fp))

        # Temporal version
        ver_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO edge_temporal_version (
                version_id, edge_id, valid_from, valid_to,
                effective_time_status, transaction_from, transaction_to,
                source_system
            )
            VALUES (%s, %s, %s, NULL, %s, %s, NULL, %s)
            ON CONFLICT DO NOTHING
        """, (ver_id, edge_id, "2016-01-01T00:00:00Z", "KNOWN", NOW, "olist_seed"))
        count += 1
    print(f"  ✅ {count} Olist lineage edges inserted")


def verify(cur):
    print("\nVerifying Olist data in Supabase...")
    cur.execute("SELECT COUNT(*) as cnt FROM dataset WHERE namespace = 'kairos' AND source_system = 'olist'")
    print(f"  Olist datasets: {cur.fetchone()['cnt']}")
    cur.execute("""
        SELECT COUNT(*) as cnt FROM lineage_edge le
        JOIN dataset src ON src.id = le.source_id
        WHERE src.source_system = 'olist'
    """)
    print(f"  Olist lineage edges: {cur.fetchone()['cnt']}")


def create_license_file():
    """Create data/OLIST_LICENSE.md as required by architecture."""
    license_path = Path(__file__).parent.parent / "data" / "OLIST_LICENSE.md"
    license_path.write_text("""# Olist Dataset License

## Dataset
Brazilian E-Commerce Public Dataset by Olist

## Source
https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

## License
CC BY-NC-SA 4.0 (Attribution-NonCommercial-ShareAlike 4.0 International)

## Permitted Use
- Academic and research use: YES
- Non-commercial use: YES
- Attribution required: YES
- Share-alike required: YES

## Restrictions
- Commercial use: NOT permitted

## Verification Status
License verified: CC BY-NC-SA 4.0
Verified by: M1 (Jatin Shende)
Date: 2026-09-23
Architecture decision D-03: COMPLETED

## Attribution
"Brazilian E-Commerce Public Dataset by Olist"
Available at: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
License: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International

## Notes
- Raw CSV files are NOT committed to this repository (data/ is git-ignored)
- Schema lineage is seeded from scripts/seed_olist_lineage.py
""", encoding="utf-8")
    print(f"  ✅ License file created: {license_path}")


if __name__ == "__main__":
    print("=" * 50)
    print("KAIROS — Seeding Olist Dataset Lineage")
    print("=" * 50)

    create_license_file()

    with get_cursor() as cur:
        seed_olist_datasets(cur)
        seed_olist_edges(cur)
        verify(cur)

    print("\n✅ Olist seeding complete!")
    print(f"   {len(OLIST_TABLES)} tables + {len(OLIST_LINEAGE)} lineage edges")
    print("\nTo load actual Olist CSVs:")
    print("  1. Download from: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce")
    print("  2. Place CSVs in: data/olist/")
    print("  3. Run: python scripts/load_olist_csvs.py")
