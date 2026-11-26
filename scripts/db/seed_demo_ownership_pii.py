"""Seed ownership and PII coverage for the authenticated Kairos demo workspace.

The catalog import adapters carried structure but no ownership or privacy
metadata, so the Assets table showed every asset as Unassigned and the PII
screen had one row.  This script assigns named owners/stewards, descriptions
and tags to every imported asset, and records a curated set of PII
classifications for the customer and payment assets.

Owners are the real project users already present in Supabase Auth.  Only the
member of this workspace (Pranav Samal) is stored as an ``owner_id``; the other
owner names are descriptive assignments until those people are added to the
workspace, so no access is silently granted.

Workspaces with only a subset of the imports (for example a two-asset upload
workspace) can be seeded with ``--allow-partial``. Missing assets are reported
and skipped instead of aborting the whole run; a PII row whose source column is
absent is recorded at asset level so the privacy review is still explicit.

Usage
-----
    python scripts/db/seed_demo_ownership_pii.py --workspace <uuid>
    python scripts/db/seed_demo_ownership_pii.py --workspace <uuid> --dry-run
    python scripts/db/seed_demo_ownership_pii.py --workspace <uuid> --allow-partial
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import Json, RealDictCursor

ROOT = Path(__file__).resolve().parents[2]
DEMO_OWNER = "Pranav Samal"
REVENUE_OWNER = "Jatin Shende"
FINANCE_OWNER = "Gauree Hatkar"

ASSETS = (
    # name, asset_type, owner, steward, description, tags
    ("customers", "TABLE", DEMO_OWNER, "Customer Data Steward",
     "Customer master with identity and contact attributes used by revenue analytics.",
     ["customer", "master-data", "pii", "gold"]),
    ("customer_retention_portal", "DASHBOARD", DEMO_OWNER, "Customer Data Steward",
     "Customer retention dashboard for churn, cohort and lifetime-value monitoring.",
     ["dashboard", "customer", "retention"]),
    ("stg_customer_360", "VIEW", DEMO_OWNER, "Customer Data Steward",
     "Staging view joining customer identity, segment and lifetime value.",
     ["staging", "customer", "pii"]),
    ("customer_transactions_schema", "TABLE", REVENUE_OWNER, "Revenue Data Steward",
     "Transaction schema imported from the payments export; one row per settled order.",
     ["revenue", "payments", "silver"]),
    ("customer_transactions_schema.csv", "FILE", REVENUE_OWNER, "Revenue Data Steward",
     "CSV header fixture used to import the transaction schema.",
     ["import", "fixture", "csv"]),
    ("orders_feed", "TABLE", REVENUE_OWNER, "Revenue Data Steward",
     "Order lifecycle events from the commerce platform.",
     ["orders", "commerce", "silver"]),
    ("payments_feed", "TABLE", REVENUE_OWNER, "Revenue Data Steward",
     "Settled payment events from the payment gateway.",
     ["payments", "finance", "pii", "silver"]),
    ("stg_orders_enriched", "VIEW", REVENUE_OWNER, "Revenue Data Steward",
     "Staging view enriching orders with payment, tax and settlement fields.",
     ["staging", "orders", "payments"]),
    ("fct_daily_revenue", "MODEL", FINANCE_OWNER, "Finance Analytics Steward",
     "Certified daily revenue mart with GMV, net recognized revenue and order counts.",
     ["revenue", "certified", "gold"]),
    ("dim_customer_segments", "MODEL", FINANCE_OWNER, "Finance Analytics Steward",
     "Customer segment dimension with lifetime value and recency bands.",
     ["customer", "segment", "gold"]),
    ("daily_revenue_kpi", "TABLE", FINANCE_OWNER, "Finance Analytics Steward",
     "Dashboard-ready daily revenue KPI table.",
     ["revenue", "kpi", "gold"]),
    ("daily_revenue_kpi", "DASHBOARD", FINANCE_OWNER, "Finance Analytics Steward",
     "Executive revenue KPI dashboard.",
     ["dashboard", "revenue", "executive"]),
    ("daily_revenue_kpi", "EXPOSURE", FINANCE_OWNER, "Finance Analytics Steward",
     "dbt exposure declaring the executive revenue dashboard consumer.",
     ["dbt", "exposure", "revenue"]),
    ("dbt_production_manifest.json", "FILE", REVENUE_OWNER, "Revenue Data Steward",
     "dbt production manifest imported to establish model dependencies.",
     ["import", "dbt", "manifest"]),
    ("enterprise_metadata_graph.json", "FILE", DEMO_OWNER, "Data Governance Steward",
     "Enterprise metadata graph fixture imported as the catalog baseline.",
     ["import", "metadata", "fixture"]),
    ("enterprise_lineage_pipeline.sql", "FILE", REVENUE_OWNER, "Revenue Data Steward",
     "SQL pipeline fixture used for static SQL lineage analysis.",
     ["import", "sql", "lineage"]),
)

# dataset name, asset type, column, classification, evidence, provenance note
PII = (
    ("customers", "TABLE", "email", "PII_SOURCE", "OBSERVED", "Direct customer email in the customer master."),
    ("customers", "TABLE", "phone_number", "PII_SOURCE", "OBSERVED", "Direct customer phone number."),
    ("customers", "TABLE", "full_name", "PII_SOURCE", "OBSERVED", "Direct customer name."),
    ("customers", "TABLE", "customer_id", "PII_SOURCE", "OBSERVED", "Stable customer identifier."),
    ("customer_transactions_schema", "TABLE", "customer_id", "PII_INHERITED", "POSSIBLE", "Customer key inherited from the customer master."),
    ("customer_transactions_schema", "TABLE", "risk_score", "PII_POTENTIAL", "POSSIBLE", "Risk score may expose financial or behavioural personal data."),
    ("orders_feed", "TABLE", "customer_id", "PII_INHERITED", "POSSIBLE", "Customer key inherited from the customer master."),
    ("payments_feed", "TABLE", "payment_id", "PII_SOURCE", "OBSERVED", "Payment identifier linked to a person."),
    ("payments_feed", "TABLE", "payment_method", "PII_SOURCE", "OBSERVED", "Payment instrument metadata."),
    ("stg_customer_360", "VIEW", "email", "PII_SOURCE", "OBSERVED", "Email projected from the customer master."),
    ("stg_customer_360", "VIEW", "masked_email", "PII_MASKED", "OBSERVED", "Masked email projected into the staging view."),
    ("stg_customer_360", "VIEW", "customer_id", "PII_INHERITED", "POSSIBLE", "Customer key inherited from the customer master."),
    ("stg_orders_enriched", "VIEW", "customer_id", "PII_INHERITED", "POSSIBLE", "Customer key inherited from orders."),
    ("dim_customer_segments", "MODEL", "customer_id", "PII_INHERITED", "POSSIBLE", "Customer key inherited into the segment dimension."),
    ("fct_daily_revenue", "MODEL", None, "PII_CLEARED", "OBSERVED", "Aggregate revenue mart; reviewed and contains no person-level fields."),
    ("daily_revenue_kpi", "TABLE", None, "PII_CLEARED", "OBSERVED", "Aggregate KPI table; reviewed and contains no person-level fields."),
    ("daily_revenue_kpi", "DASHBOARD", None, "PII_CLEARED", "OBSERVED", "Aggregate executive dashboard; reviewed and contains no person-level fields."),
    ("daily_revenue_kpi", "EXPOSURE", None, "PII_CLEARED", "OBSERVED", "dbt exposure metadata; reviewed and contains no person-level fields."),
    ("customer_retention_portal", "DASHBOARD", None, "PII_INHERITED", "POSSIBLE", "Retention dashboard exposes customer cohort metrics derived from the customer master."),
    ("customer_transactions_schema.csv", "FILE", None, "PII_INHERITED", "POSSIBLE", "CSV header fixture mirrors the customer-keyed transaction schema."),
    ("dbt_production_manifest.json", "FILE", None, "PII_CLEARED", "OBSERVED", "dbt manifest metadata; reviewed and contains no person-level fields."),
    ("enterprise_metadata_graph.json", "FILE", None, "PII_CLEARED", "OBSERVED", "Metadata graph fixture; reviewed and contains no person-level fields."),
    ("enterprise_lineage_pipeline.sql", "FILE", None, "PII_CLEARED", "OBSERVED", "SQL lineage fixture; reviewed and contains no person-level fields."),
)

ORIGIN = {
    "PII_INHERITED": "inherited_lineage",
    "PII_POTENTIAL": "sqlglot_possible",
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, help="Workspace UUID to seed")
    parser.add_argument("--dry-run", action="store_true", help="Report without writing")
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Skip assets or columns that are not present in this workspace instead of failing",
    )
    args = parser.parse_args(argv)

    load_dotenv(dotenv_path=str(ROOT / ".env"))
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        print("ERROR: DATABASE_URL is not set.", file=sys.stderr)
        return 2

    if args.dry_run:
        print(f"DRY RUN: {len(ASSETS)} ownership assignments and {len(PII)} PII classifications.")
        return 0

    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT set_config('kairos.workspace_id', %s, true)", (args.workspace,))
            cur.execute(
                """
                SELECT wm.user_id::text, u.email,
                       COALESCE(u.raw_user_meta_data->>'full_name', u.raw_user_meta_data->>'name', u.email) AS display_name
                FROM workspace_member wm
                LEFT JOIN auth.users u ON u.id = wm.user_id
                WHERE wm.workspace_id=%s::uuid AND wm.status='active' AND wm.role='owner'
                ORDER BY wm.created_at LIMIT 1
                """,
                (args.workspace,),
            )
            member = cur.fetchone()
            if not member:
                raise RuntimeError("No active workspace owner to attribute the seeded records to")
            actor = member["user_id"]
            actor_name = (member.get("display_name") or member.get("email") or "").strip()

            updated = 0
            skipped_assets = []
            for name, asset_type, owner, steward, description, tags in ASSETS:
                owner_id = actor if owner == DEMO_OWNER or owner.casefold() == actor_name.casefold() else None
                cur.execute(
                    """
                    UPDATE dataset
                       SET owner_name=%s, owner_id=%s, steward_name=%s,
                           description=%s, tags=%s,
                           assigned_by=%s, assigned_at=now(),
                           last_modified_by='demo-ownership-seed', last_modified_at=now()
                     WHERE workspace_id=%s::uuid AND name=%s AND asset_type=%s
                       AND removed_at IS NULL
                    """,
                    (owner, owner_id, steward, description, tags, actor, args.workspace, name, asset_type),
                )
                if cur.rowcount:
                    updated += cur.rowcount
                elif args.allow_partial:
                    skipped_assets.append(f"{name} ({asset_type})")
                else:
                    raise RuntimeError(f"Asset not found: {name} ({asset_type})")

            cur.execute("DELETE FROM pii_classification WHERE workspace_id=%s::uuid", (args.workspace,))
            inserted = 0
            skipped_pii = []
            for name, asset_type, column, classification, evidence, note in PII:
                # A name/type can have more than one physical import row (the
                # SQL fixture was committed twice).  Classify every visible
                # variant, otherwise one row remains "Not classified".
                cur.execute(
                    "SELECT id::text FROM dataset WHERE workspace_id=%s::uuid AND name=%s AND asset_type=%s AND removed_at IS NULL",
                    (args.workspace, name, asset_type),
                )
                datasets = cur.fetchall()
                if not datasets:
                    if args.allow_partial:
                        skipped_pii.append(f"{name} ({asset_type}) [{classification}]")
                        continue
                    raise RuntimeError(f"Asset not found: {name} ({asset_type})")
                for dataset in datasets:
                    column_id = None
                    if column:
                        cur.execute(
                            "SELECT cr.id::text FROM column_record cr "
                            "WHERE cr.dataset_id=%s::uuid AND cr.column_name=%s LIMIT 1",
                            (dataset["id"], column),
                        )
                        column_row = cur.fetchone()
                        if column_row:
                            column_id = column_row["id"]
                        elif args.allow_partial:
                            # The import did not retain this column; keep the
                            # classification at asset level so the review is
                            # still visible instead of silently disappearing.
                            skipped_pii.append(f"{name}.{column} (classified at asset level)")
                        else:
                            raise RuntimeError(f"Column not found: {name}.{column}")
                    origin = ORIGIN.get(classification, "manual_steward")
                    provenance = Json({"origin": origin, "note": note, "seed": "demo-ownership-pii-v1"})
                    reviewed = classification == "PII_CLEARED"
                    cur.execute(
                        """
                        INSERT INTO pii_classification
                            (workspace_id, dataset_id, column_id, classification,
                             evidence_state, provenance, classified_by, reviewed_by, reviewed_at)
                        VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s::uuid, %s, %s)
                        """,
                        (
                            args.workspace, dataset["id"], column_id, classification, evidence,
                            provenance, actor, actor if reviewed else None,
                            datetime.now(timezone.utc) if reviewed else None,
                        ),
                    )
                    inserted += 1

            # Domain and product records already carry an owner column; point
            # them at the active workspace owner so the governance screens do
            # not show a second class of unowned records.
            cur.execute(
                "UPDATE domain SET owner_user_id=%s::uuid WHERE workspace_id=%s::uuid AND owner_user_id IS NULL",
                (actor, args.workspace),
            )
            cur.execute(
                "UPDATE data_product SET owner_user_id=%s::uuid WHERE workspace_id=%s::uuid AND owner_user_id IS NULL",
                (actor, args.workspace),
            )
        conn.commit()
        print(f"Updated {updated} asset rows and inserted {inserted} PII classifications into {args.workspace}.")
        if skipped_assets:
            print(f"Skipped {len(skipped_assets)} absent assets: {', '.join(skipped_assets)}")
        if skipped_pii:
            print(f"Partial PII: {', '.join(skipped_pii)}")
        return 0
    except Exception as exc:
        conn.rollback()
        print(f"FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
