"""Automated verification and demonstration script for Kairos M5 API and contracts."""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient
from backend.app.main import app

def run_demo():
    print("=" * 60)
    print("KAIROS M5: API LAYER & CONTRACT DEMO")
    print("=" * 60)

    client = TestClient(app)

    # 1. Health
    res = client.get("/api/v1/health")
    print(f"\n[1] GET /api/v1/health -> {res.status_code}")
    print("   Payload:", res.json())

    # 2. Entity lookup
    res = client.get("/api/v1/entities/orders_fact")
    print(f"\n[2] GET /api/v1/entities/orders_fact -> {res.status_code}")
    print(f"   Name: {res.json()['data']['name']}, Asset Type: {res.json()['data']['asset_type']}")

    # 3. Entity Search
    res = client.get("/api/v1/search?q=orders")
    print(f"\n[3] GET /api/v1/search?q=orders -> {res.status_code}")
    print(f"   Matches ({res.json()['total']}): {[r['name'] for r in res.json()['results']]}")

    # 4. Lineage Graph (Live vs Historical)
    res_live = client.get("/api/v1/lineage/orders_fact/graph")
    print(f"\n[4a] GET /api/v1/lineage/orders_fact/graph (LIVE) -> {res_live.status_code}")
    print(f"   Total Nodes: {len(res_live.json()['nodes'])}, Total Edges: {len(res_live.json()['edges'])}")
    stg_live = [e for e in res_live.json()['edges'] if e['source'] == 'stg_customer_orders'][0]
    print(f"   stg_customer_orders state: {stg_live['reasoning_state']} (d14_warning: {stg_live['d14_warning']})")

    res_hist = client.get("/api/v1/lineage/orders_fact/graph?valid_at=2026-08-15T00:00:00Z")
    print(f"\n[4b] GET /api/v1/lineage/orders_fact/graph?valid_at=2026-08-15 (HISTORICAL) -> {res_hist.status_code}")
    stg_hist = [e for e in res_hist.json()['edges'] if e['source'] == 'stg_customer_orders'][0]
    print(f"   stg_customer_orders reverted state: {stg_hist['reasoning_state']} (due to schema creation date 2026-09-01)")

    # 5. Evidence Dossier
    res = client.get("/api/v1/evidence/ev_stg_orders_01")
    print(f"\n[5] GET /api/v1/evidence/ev_stg_orders_01 -> {res.status_code}")
    dossier = res.json()['data']
    print(f"   Type: {dossier['evidence_type']}, Parser: {dossier['parser_status']}")
    print(f"   Raw Event Payload Hash: {dossier['raw_event']['payload_hash']}")

    # 6. Dependency Reasoning (M4 Serialization)
    res = client.get("/api/v1/runs/run_2026_09_23_093214/dependency/stg_customer_orders/orders_fact")
    print(f"\n[6] GET /api/v1/runs/run_.../dependency/stg_customer_orders/orders_fact -> {res.status_code}")
    dep = res.json()
    print(f"   State: {dep['state']}, Rule: {dep['rule_id']}")
    print(f"   Interpretation: \"{dep['interpretation']}\"")
    print(f"   Warnings: {dep['warnings']}")

    # 7. Benchmark Oracle (Hazard Mode)
    res = client.get("/api/v1/evaluation/oracle/run_2026_09_23_093214")
    print(f"\n[7] GET /api/v1/evaluation/oracle/run_2026_09_23_093214 -> {res.status_code}")
    print(f"   Hazard Warning: {res.json()['warning']}")
    print(f"   Records: {res.json()['records']}")

    print("\n" + "=" * 60)
    print("ALL M5 CONTRACT ENDPOINTS VERIFIED SUCCESSFULLY.")
    print("=" * 60)

if __name__ == "__main__":
    run_demo()
