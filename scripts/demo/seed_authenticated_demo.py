#!/usr/bin/env python
"""Seed or synchronize the authenticated enterprise demo data for Demo 3.

Populates or verifies:
1. Enterprise Pipeline assets and multi-tier lineage edges (Raw -> Staging -> Marts -> Dashboards)
2. Business Domains (Finance & Revenue, Customer Management)
3. Business Glossary Terms (GMV, Net Recognized Revenue, Customer LTV, PII) and dataset mappings
4. Enterprise Data Products (Executive Revenue Intelligence, Customer 360 Mart) with contracts
5. PII Classifications with provenance
6. Freshness SLAs for daily revenue reporting

Usage:
    python scripts/demo/seed_authenticated_demo.py [--workspace-id UUID] [--user-id UUID]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import Json, RealDictCursor

from backend.app.identity.canonical_ids import canonical_import_identity
from ingestion.static_files import parse_static_file


def _declared_valid_from(payload: dict) -> tuple[datetime | None, str]:
    """Use the dbt manifest's own generated_at as valid time when present."""
    raw = (payload.get("provenance") or {}).get("dbt_generated_at")
    if not isinstance(raw, str) or not raw.strip():
        return None, "UNKNOWN"
    try:
        value = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None, "UNKNOWN"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value, "KNOWN"


def seed_workspace(conn, workspace_id: str, user_id: str) -> dict:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Set workspace and user scope
        cur.execute("SET LOCAL kairos.workspace_id = %s", (workspace_id,))
        cur.execute("SET LOCAL kairos.user_id = %s", (user_id,))

        print(f"[*] Scoped to workspace: {workspace_id}")
        print(f"[*] Actor user: {user_id}")

        # 1. Load and parse enterprise_metadata_graph.json
        fixture_path = os.path.join("demo-authenticated-ingestion", "enterprise_metadata_graph.json")
        with open(fixture_path, "r", encoding="utf-8") as f:
            raw_meta = json.load(f)

        parsed = parse_static_file("metadata_graph", raw_meta, filename="enterprise_metadata_graph.json")
        if not parsed.ok or not parsed.payload:
            raise RuntimeError(f"Failed to parse metadata graph: {[d.message for d in parsed.diagnostics]}")

        payload = parsed.payload
        content_hash = payload["provenance"]["content_sha256"]
        source_kind = "upload"
        source_ref = "demo-authenticated-ingestion/enterprise_metadata_graph.json"

        # 2. Insert or retrieve import_run
        idempotency_key = f"demo3-authenticated-seed-{workspace_id}"
        cur.execute(
            """
            INSERT INTO import_run
                (actor_user_id, idempotency_key, source_kind, source_ref,
                 content_sha256, contract_version, adapter_name, adapter_version,
                 status, result_summary)
            VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, 'COMMITTED', %s)
            ON CONFLICT (workspace_id, idempotency_key)
            DO UPDATE SET status = 'COMMITTED'
            RETURNING id::text
            """,
            (
                user_id, idempotency_key, source_kind, source_ref,
                content_hash, payload["contract_version"],
                payload["provenance"]["adapter"], payload["provenance"]["adapter_version"],
                Json({"seeded": True, "fixture": "enterprise_metadata_graph.json"}),
            ),
        )
        import_id = cur.fetchone()["id"]
        raw_event_id = f"kairos-import:{import_id}"

        # 3. Insert raw event
        cur.execute(
            """
            INSERT INTO raw_event (event_id, payload, payload_hash, source_system)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (event_id) DO NOTHING
            """,
            (raw_event_id, Json(payload), content_hash, source_kind),
        )

        # 4. Upsert assets and columns
        declared_valid_from, effective_time_status = _declared_valid_from(payload)
        dataset_ids: dict[str, str] = {}
        for asset in payload["assets"]:
            namespace = str(asset.get("namespace") or "general")
            name = str(asset.get("name") or asset["qualified_name"].rsplit("/", 1)[-1])
            database_name, schema_name, asset_type = canonical_import_identity(asset)

            cur.execute(
                """
                SELECT public.kairos_upsert_dataset(%s, %s, %s, %s, %s, %s)::text AS id
                """,
                (source_kind, namespace, database_name, schema_name, name, asset_type),
            )
            ds_id = cur.fetchone()["id"]
            dataset_ids[asset["id"]] = ds_id

            # Insert columns
            columns = asset.get("metadata", {}).get("columns", [])
            for col in columns:
                if isinstance(col, dict) and col.get("name"):
                    cur.execute(
                        """
                        INSERT INTO column_record (dataset_id, column_name, data_type)
                        VALUES (%s::uuid, %s, %s)
                        ON CONFLICT (dataset_id, schema_version, column_name)
                        DO UPDATE SET data_type = EXCLUDED.data_type
                        """,
                        (ds_id, col["name"], col.get("data_type")),
                    )

        print(f"[+] Upserted {len(dataset_ids)} enterprise dataset assets and columns")

        # 5. Insert lineage edges and evidence
        edges_inserted = 0
        for index, rel in enumerate(payload["relationships"]):
            s_id = dataset_ids[rel["source_id"]]
            t_id = dataset_ids[rel["target_id"]]
            edge_type = rel["edge_type"]

            cur.execute(
                """
                INSERT INTO lineage_edge (source_id, target_id, granularity, operator_fingerprint)
                VALUES (%s::uuid, %s::uuid, 'DATASET', %s)
                ON CONFLICT DO NOTHING
                RETURNING id::text
                """,
                (s_id, t_id, edge_type),
            )
            edge_row = cur.fetchone()
            if edge_row:
                edge_id = edge_row["id"]
            else:
                cur.execute(
                    """
                    SELECT id::text FROM lineage_edge
                    WHERE source_id = %s::uuid AND target_id = %s::uuid
                      AND granularity = 'DATASET'
                      AND operator_fingerprint IS NOT DISTINCT FROM %s
                    LIMIT 1
                    """,
                    (s_id, t_id, edge_type),
                )
                edge_id = cur.fetchone()["id"]

            evidence_id = f"{import_id}:{index}"
            cur.execute(
                """
                INSERT INTO evidence
                    (evidence_id, evidence_type, source_system, source_dataset_id,
                     target_dataset_id, granularity, parser_status, diagnostics, raw_event_id)
                VALUES (%s, 'STATIC_DEPENDENCY', %s, %s::uuid, %s::uuid,
                        'DATASET', 'SUPPORTED', %s, %s)
                RETURNING id::text
                """,
                (evidence_id, source_kind, s_id, t_id,
                 Json({"classification": "DECLARED_METADATA", "edge_type": edge_type, "provenance": rel.get("provenance")}),
                 raw_event_id),
            )
            ev_row = cur.fetchone()
            norm_ev_id = ev_row["id"]
            cur.execute(
                """
                INSERT INTO edge_temporal_version
                    (edge_id, valid_from, effective_time_status, transaction_from,
                     evidence_id, source_system)
                VALUES (%s::uuid, COALESCE(%s::timestamptz, now()), %s, now(), %s::uuid, %s)
                """,
                (edge_id, declared_valid_from, effective_time_status,
                 norm_ev_id, source_kind),
            )
            edges_inserted += 1

        print(f"[+] Upserted {edges_inserted} dependency lineage edges with evidence")

        # 6. Seed Domains
        domains_data = [
            ("Finance & Revenue", "Enterprise accounting, revenue recognition, accounts receivable, and financial compliance."),
            ("Customer Management", "Customer identity, onboarding, loyalty, and CRM lifecycle records."),
        ]
        domain_ids = {}
        for d_name, d_desc in domains_data:
            cur.execute(
                """
                INSERT INTO domain (name, description, created_by)
                VALUES (%s, %s, %s::uuid)
                ON CONFLICT (workspace_id, name)
                DO UPDATE SET description = EXCLUDED.description
                RETURNING id::text
                """,
                (d_name, d_desc, user_id),
            )
            domain_ids[d_name] = cur.fetchone()["id"]

        print(f"[+] Seeded {len(domain_ids)} Governance Domains")

        # 7. Seed Glossary Terms & Link to Datasets
        terms_data = [
            ("Gross Merchandise Value (GMV)", "Total sales monetary value for merchandise sold through the enterprise platform prior to fees, returns, or expenses.", "APPROVED", ["mrt-rev-06", "stg-ord-04"]),
            ("Net Recognized Revenue", "Actual GAAP revenue recognized in accordance with ASC 606 / IFRS 15 following completed delivery and payment settlement.", "APPROVED", ["mrt-rev-06"]),
            ("Customer Lifetime Value (LTV)", "Discounted present value of the future net profit stream attributable to a customer account over their lifetime.", "APPROVED", ["mrt-cust-07"]),
            ("Personally Identifiable Information (PII)", "Information that can identify, contact, or locate an individual, requiring masking and strict GDPR/CCPA controls.", "APPROVED", ["raw-cust-01"]),
        ]
        term_count = 0
        assignment_count = 0
        for t_name, t_def, t_status, linked_asset_keys in terms_data:
            cur.execute(
                """
                INSERT INTO glossary_term (name, definition, status, created_by, approved_by)
                VALUES (%s, %s, %s, %s::uuid, %s::uuid)
                ON CONFLICT (workspace_id, name)
                DO UPDATE SET definition = EXCLUDED.definition, status = EXCLUDED.status
                RETURNING id::text
                """,
                (t_name, t_def, t_status, user_id, user_id),
            )
            term_id = cur.fetchone()["id"]
            term_count += 1

            for a_key in linked_asset_keys:
                if a_key in dataset_ids:
                    ds_id = dataset_ids[a_key]
                    cur.execute(
                        """
                        INSERT INTO term_assignment (term_id, dataset_id, assigned_by)
                        VALUES (%s::uuid, %s::uuid, %s::uuid)
                        ON CONFLICT (workspace_id, term_id, dataset_id) DO NOTHING
                        """,
                        (term_id, ds_id, user_id),
                    )
                    assignment_count += 1

        print(f"[+] Seeded {term_count} Glossary Terms and {assignment_count} Term Assignments")

        # 8. Seed Data Products & Contracts
        products_data = [
            (
                "Executive Revenue Intelligence Product",
                "Certified daily enterprise revenue stream powering board KPI dashboards and financial audit packs.",
                domain_ids["Finance & Revenue"],
                ["mrt-rev-06", "dsh-rev-08"],
            ),
            (
                "Customer 360 Intelligence Mart",
                "Conformed and pseudonymized customer dimensions powering lifecycle segmentation and retention analytics.",
                domain_ids["Customer Management"],
                ["stg-cust-05", "mrt-cust-07", "dsh-ret-09"],
            ),
        ]
        for p_name, p_desc, dom_id, p_asset_keys in products_data:
            cur.execute(
                """
                INSERT INTO data_product (name, description, domain_id, status, created_by)
                VALUES (%s, %s, %s::uuid, 'ACTIVE', %s::uuid)
                ON CONFLICT (workspace_id, name)
                DO UPDATE SET description = EXCLUDED.description, domain_id = EXCLUDED.domain_id, status = 'ACTIVE'
                RETURNING id::text
                """,
                (p_name, p_desc, dom_id, user_id),
            )
            prod_id = cur.fetchone()["id"]

            # Bind product assets
            for a_key in p_asset_keys:
                if a_key in dataset_ids:
                    ds_id = dataset_ids[a_key]
                    cur.execute(
                        """
                        INSERT INTO product_asset (product_id, dataset_id)
                        VALUES (%s::uuid, %s::uuid)
                        ON CONFLICT (workspace_id, product_id, dataset_id) DO NOTHING
                        """,
                        (prod_id, ds_id),
                    )

            # Insert Data Contract
            cur.execute(
                """
                INSERT INTO data_contract (product_id, version, enforcement_mode, clauses, created_by)
                VALUES (%s::uuid, 1, 'BLOCK', %s, %s::uuid)
                ON CONFLICT (workspace_id, product_id, version) DO NOTHING
                """,
                (
                    prod_id,
                    Json([
                        {"rule": "freshness", "max_lag_seconds": 86400},
                        {"rule": "schema_freeze", "breaking_change_policy": "reject"},
                        {"rule": "sox_audit", "certified": True},
                    ]),
                    user_id,
                ),
            )

        print("[+] Seeded 2 Data Products with Active Contracts and SLA Assertions")

        # 9. Seed PII Classifications
        if "raw-cust-01" in dataset_ids:
            cust_ds = dataset_ids["raw-cust-01"]
            cur.execute("SELECT id::text FROM column_record WHERE dataset_id = %s::uuid AND column_name = 'email'", (cust_ds,))
            email_col = cur.fetchone()
            if email_col:
                cur.execute(
                    """
                    INSERT INTO pii_classification
                        (dataset_id, column_id, classification, evidence_state, provenance, classified_by)
                    VALUES (%s::uuid, %s::uuid, 'PII_SOURCE', 'OBSERVED', %s, %s::uuid)
                    """,
                    (
                        cust_ds, email_col["id"],
                        Json({"origin": "manual_steward", "note": "Customer legal email address verified via ERP sync"}),
                        user_id,
                    ),
                )
                print("[+] Recorded PII classification on raw_enterprise.customers.email")

        # 10. Seed Freshness SLAs
        if "mrt-rev-06" in dataset_ids:
            rev_ds = dataset_ids["mrt-rev-06"]
            cur.execute(
                """
                INSERT INTO freshness_sla
                    (dataset_id, warn_after_minutes, error_after_minutes, signal, evaluation_schedule)
                VALUES (%s::uuid, 1200, 1440, 'manual', 'hourly')
                ON CONFLICT (workspace_id, dataset_id)
                DO UPDATE SET warn_after_minutes = 1200, error_after_minutes = 1440, evaluation_schedule = 'hourly'
                """,
                (rev_ds,),
            )
            cur.execute("SELECT id::text FROM freshness_sla WHERE dataset_id = %s::uuid", (rev_ds,))
            sla_row = cur.fetchone()
            sla_id = sla_row["id"] if sla_row else None
            cur.execute(
                """
                INSERT INTO freshness_evaluation
                    (dataset_id, sla_id, state, last_source_activity_at, evaluated_at,
                     age_minutes, threshold_minutes, reason, evaluation_mode, evidence_ref)
                VALUES (%s::uuid, %s::uuid, 'HEALTHY', now(), now(),
                        120, 1440, 'Runtime activity confirmed within 24h SLA', 'MANUAL', %s)
                """,
                (rev_ds, sla_id, Json({"source": "enterprise_revenue_pipeline", "sla_minutes": 1440})),
            )
            print("[+] Configured 24h Freshness SLA on analytics.fct_daily_revenue (HEALTHY)")

        return {
            "workspace_id": workspace_id,
            "assets_count": len(dataset_ids),
            "edges_count": edges_inserted,
            "domains": list(domain_ids.keys()),
            "terms": [t[0] for t in terms_data],
        }


def main() -> int:
    load_dotenv()
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        print("ERROR: DATABASE_URL is not set", file=sys.stderr)
        return 2

    parser = argparse.ArgumentParser(description="Seed authenticated enterprise demo data")
    parser.add_argument("--workspace-id", help="Workspace UUID to seed (defaults to active user workspace)")
    parser.add_argument("--user-id", help="User UUID (defaults to workspace owner)")
    args = parser.parse_args()

    conn = psycopg2.connect(dsn, connect_timeout=10)
    try:
        workspace_id = args.workspace_id
        user_id = args.user_id

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if not workspace_id:
                # Find an existing personal workspace
                cur.execute("SELECT id::text, owner_user_id::text FROM kairos_workspace ORDER BY created_at DESC LIMIT 1")
                row = cur.fetchone()
                if row:
                    workspace_id = row["id"]
                    user_id = user_id or row["owner_user_id"]
                else:
                    # Provision one with random UUID
                    owner = str(uuid.uuid4())
                    cur.execute("SELECT kairos_ensure_personal_workspace(%s::uuid)", (owner,))
                    workspace_id = str(cur.fetchone()[0])
                    user_id = owner

        print(f"Seeding authenticated demo for workspace={workspace_id}, user={user_id}...")
        result = seed_workspace(conn, workspace_id, user_id)
        conn.commit()

        print("\n==================================================================")
        print("Authenticated Enterprise Demo Data Seeding Complete!")
        print("==================================================================")
        print(f"Workspace ID : {result['workspace_id']}")
        print(f"Assets       : {result['assets_count']} conformed datasets across 4 tiers")
        print(f"Edges        : {result['edges_count']} multi-stage lineage relationships")
        print(f"Domains      : {', '.join(result['domains'])}")
        print(f"Glossary     : {', '.join(result['terms'])}")
        print("==================================================================\n")
        return 0
    except Exception as exc:
        conn.rollback()
        print(f"\nERROR during seeding: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
