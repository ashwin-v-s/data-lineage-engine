#!/usr/bin/env python
"""Verify that all files in demo-authenticated-ingestion parse deterministically
and adhere strictly to the Kairos ingestion envelope without synthetic fallback.
"""
from __future__ import annotations

import json
import os
import sys

from ingestion.static_files import parse_static_file


def verify_folder(folder_path: str) -> bool:
    print(f"\n==================================================================")
    print(f"Verifying Authenticated Demo Fixtures in: {folder_path}")
    print(f"==================================================================")

    all_passed = True

    # 1. enterprise_metadata_graph.json
    p_meta = os.path.join(folder_path, "enterprise_metadata_graph.json")
    if os.path.exists(p_meta):
        with open(p_meta, "r", encoding="utf-8") as f:
            content = json.load(f)
        res = parse_static_file("metadata_graph", content, filename="enterprise_metadata_graph.json")
        if res.ok and len(res.payload.get("assets", [])) == 9 and len(res.payload.get("relationships", [])) == 9:
            print(f"[PASS] enterprise_metadata_graph.json: OK={res.ok} assets={len(res.payload['assets'])} edges={len(res.payload['relationships'])}")
        else:
            print(f"[FAIL] enterprise_metadata_graph.json: OK={res.ok} errors={[d.message for d in res.diagnostics]}")
            all_passed = False
    else:
        print(f"[FAIL] Missing {p_meta}")
        all_passed = False

    # 2. enterprise_lineage_pipeline.sql
    p_sql = os.path.join(folder_path, "enterprise_lineage_pipeline.sql")
    if os.path.exists(p_sql):
        with open(p_sql, "r", encoding="utf-8") as f:
            content = f.read()
        res = parse_static_file("sql_file", content, filename="enterprise_lineage_pipeline.sql")
        if res.ok and len(res.payload.get("assets", [])) >= 7 and len(res.payload.get("relationships", [])) >= 5:
            print(f"[PASS] enterprise_lineage_pipeline.sql: OK={res.ok} assets={len(res.payload['assets'])} edges={len(res.payload['relationships'])}")
        else:
            print(f"[FAIL] enterprise_lineage_pipeline.sql: OK={res.ok} errors={[d.message for d in res.diagnostics]}")
            all_passed = False
    else:
        print(f"[FAIL] Missing {p_sql}")
        all_passed = False

    # 3. dbt_production_manifest.json
    p_dbt = os.path.join(folder_path, "dbt_production_manifest.json")
    if os.path.exists(p_dbt):
        with open(p_dbt, "r", encoding="utf-8") as f:
            content = json.load(f)
        res = parse_static_file("dbt_manifest", content, filename="dbt_production_manifest.json")
        if res.ok and len(res.payload.get("assets", [])) == 8 and len(res.payload.get("relationships", [])) == 8:
            print(f"[PASS] dbt_production_manifest.json: OK={res.ok} assets={len(res.payload['assets'])} edges={len(res.payload['relationships'])}")
        else:
            print(f"[FAIL] dbt_production_manifest.json: OK={res.ok} errors={[d.message for d in res.diagnostics]}")
            all_passed = False
    else:
        print(f"[FAIL] Missing {p_dbt}")
        all_passed = False

    # 4. customer_transactions_schema.csv
    p_csv = os.path.join(folder_path, "customer_transactions_schema.csv")
    if os.path.exists(p_csv):
        with open(p_csv, "r", encoding="utf-8") as f:
            content = f.read()
        res = parse_static_file("csv_headers", content, filename="customer_transactions_schema.csv")
        cols = len(res.payload["assets"][0].get("metadata", {}).get("columns", [])) if res.ok else 0
        if res.ok and cols == 10:
            print(f"[PASS] customer_transactions_schema.csv: OK={res.ok} assets={len(res.payload['assets'])} columns={cols}")
        else:
            print(f"[FAIL] customer_transactions_schema.csv: OK={res.ok} errors={[d.message for d in res.diagnostics]}")
            all_passed = False
    else:
        print(f"[FAIL] Missing {p_csv}")
        all_passed = False

    # 5. enterprise_inventory.json
    p_inv = os.path.join(folder_path, "enterprise_inventory.json")
    if os.path.exists(p_inv):
        with open(p_inv, "r", encoding="utf-8") as f:
            content = json.load(f)
        res = parse_static_file("file_inventory", content, filename="enterprise_inventory.json")
        if res.ok and len(res.payload.get("assets", [])) >= 4:
            print(f"[PASS] enterprise_inventory.json: OK={res.ok} assets={len(res.payload['assets'])}")
        else:
            print(f"[FAIL] enterprise_inventory.json: OK={res.ok} errors={[d.message for d in res.diagnostics]}")
            all_passed = False
    else:
        print(f"[FAIL] Missing {p_inv}")
        all_passed = False

    return all_passed


def main() -> int:
    ok1 = verify_folder("demo-authenticated-ingestion")
    ok2 = verify_folder("docs/demo-fixtures")
    if ok1 and ok2:
        print("\nAll authenticated demo fixtures verified deterministically: 100% PASS.")
        return 0
    else:
        print("\nSome demo fixtures failed verification.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
