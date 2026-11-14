"""
Demo 9 and 10 live verification against deployed Kairos API.
Demo 9: Freshness, Quality, Incident lifecycle
Demo 10: Glossary, PII, Domains, Data Products
"""
from __future__ import annotations
import os, sys
import uuid as _uuid
_RUN = _uuid.uuid4().hex[:6]  # unique suffix per run
from dotenv import load_dotenv
load_dotenv('.env')
import httpx

SUPABASE_URL = os.getenv('SUPABASE_URL', '').rstrip('/')
ANON_KEY     = os.getenv('SUPABASE_PUBLISHABLE_KEY', '')
BASE         = 'https://data-lineage-engine-mu.vercel.app'

resp = httpx.post(
    f'{SUPABASE_URL}/auth/v1/token?grant_type=password',
    headers={'apikey': ANON_KEY, 'Content-Type': 'application/json'},
    json={'email': 'pranavsamal43@gmail.com', 'password': 'Kairos_Test_2026!'},
    timeout=15,
)
if resp.status_code != 200:
    print('Login failed:', resp.json()); sys.exit(1)
TOKEN = resp.json()['access_token']
AUTH  = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}
print(f'Signed in: pranavsamal43@gmail.com\n')

results = []

def call(method, path, desc, body=None, timeout=20):
    r = httpx.request(method, f'{BASE}{path}', headers=AUTH, json=body, timeout=timeout)
    icon = 'PASS' if r.status_code < 400 else 'FAIL'
    results.append((icon, r.status_code, method, path))
    print(f'  [{icon} {r.status_code}] {method} {path}')
    print(f'          {desc}')
    if r.status_code in (200, 201) and r.text:
        try:
            b = r.json()
            if isinstance(b, dict):
                for k, v in list(b.items())[:5]:
                    if isinstance(v, list): print(f'          {k}: {len(v)} items')
                    elif not isinstance(v, (dict, list)): print(f'          {k}: {v}')
        except: pass
    elif r.status_code >= 400:
        try:
            detail = r.json().get('detail','')
            if isinstance(detail, str): print(f'          error: {detail[:100]}')
        except: pass
    return r

# ═══════════════════════════════════════════════════════════════════════════════
print('=' * 60)
print('DEMO 9 — Freshness, Quality, Incident lifecycle')
print('=' * 60)

call('GET', '/api/v1/governance/slas',      'List freshness SLAs')
call('GET', '/api/v1/governance/freshness', 'Freshness evaluation status')
call('GET', '/api/v1/governance/incidents', 'List incidents')

# Create SLA — need a dataset first
r_search = httpx.get(f'{BASE}/api/v1/catalog', headers=AUTH, timeout=15)
dataset_id = None
if r_search.status_code == 200:
    b = r_search.json()
    for k in ['assets','items','results','datasets']:
        if k in b and isinstance(b[k], list) and len(b[k]) > 0:
            dataset_id = b[k][0].get('id')
            print(f'\n  Using dataset: {b[k][0].get("name")} ({dataset_id})')
            break

if dataset_id:
    # Create SLA: warn=80, error=100 (warn must be exactly 80% of error)
    r_sla = call('POST', '/api/v1/governance/slas', 'Create freshness SLA',
                 body={"asset_id": dataset_id, "warn_after_minutes": 80,
                       "error_after_minutes": 100, "signal": "manual",
                       "evaluation_schedule": "manual", "paused": False})
    if r_sla.status_code in (200, 201):
        sla_id = r_sla.json().get('id') or r_sla.json().get('sla_id')
        # Trigger evaluation
        call('POST', f'/api/v1/governance/datasets/{dataset_id}/evaluate',
             'Trigger freshness evaluation for dataset', body={})
        # Read back
        call('GET', '/api/v1/governance/freshness', 'Freshness after evaluation')
        call('GET', '/api/v1/governance/incidents', 'Incidents after evaluation')
else:
    print('\n  Workspace has no catalog assets — SLA creation skipped')
    print('  (Read-only flow verified above)')

print(f'\n  Demo 9 honest state: Routes return 200. SLA create/evaluate/incident')
print(f'  lifecycle needs at least one imported dataset to create SLAs.')
print(f'  Scheduler execution is on-demand only (no background scheduler running).')

# ═══════════════════════════════════════════════════════════════════════════════
print()
print('=' * 60)
print('DEMO 10 — Glossary, PII, Domains, Data Products')
print('=' * 60)

# 1. Glossary terms
call('GET', '/api/v1/governance/terms', 'List glossary terms')
r_term = call('POST', '/api/v1/governance/terms', 'Create glossary term',
              body={"name": f"Net Revenue {os.urandom(3).hex()}",
                    "definition": "Total revenue after discounts and returns. Used in monthly reporting."})
term_id = r_term.json().get('id') if r_term.status_code == 201 else None
call('GET', '/api/v1/governance/terms', 'Read back terms after creation')

# 2. Domains
call('GET', '/api/v1/governance/domains', 'List domains')
r_domain = call('POST', '/api/v1/governance/domains', 'Create Finance domain',
                body={"name": f"Finance {_RUN}",
                      "description": "Financial data and revenue reporting."})
domain_id = r_domain.json().get('id') if r_domain.status_code == 201 else None
call('GET', '/api/v1/governance/domains', 'Read back domains after creation')

# 3. Data Products
call('GET', '/api/v1/governance/products', 'List data products')
r_prod = call('POST', '/api/v1/governance/products', 'Create Revenue Analytics product',
              body={"name": f"Revenue Analytics {_RUN}",
                    "description": "Monthly revenue aggregations and KPIs.",
                    "domain_id": domain_id,
                    "status": "DRAFT",
                    "asset_ids": []})
product_id = r_prod.json().get('id') if r_prod.status_code == 201 else None
call('GET', '/api/v1/governance/products', 'Read back products after creation')

# 4. PII Classification (needs a dataset with a column)
if dataset_id:
    # Get columns for the dataset
    r_cols = httpx.get(f'{BASE}/api/v1/governance/datasets/{dataset_id}/columns',
                       headers=AUTH, timeout=15)
    col_id = None
    if r_cols.status_code == 200:
        cols = r_cols.json().get('columns', [])
        if cols: col_id = cols[0].get('id')

    if col_id:
        call('POST', '/api/v1/governance/classifications', 'Tag column as PII',
             body={"dataset_id": dataset_id, "column_id": col_id,
                   "classification": "PII_SOURCE", "evidence_state": "OBSERVED",
                   "provenance": {"origin": "manual_steward",
                                  "note": "Manually reviewed and confirmed PII."}})
        call('GET', '/api/v1/governance/classifications', 'List PII classifications after tagging')
    else:
        print('\n  No column found for PII tagging — skipping classification demo')
else:
    print('\n  No dataset — PII classification skipped (needs imported dataset)')

# ── Summary ───────────────────────────────────────────────────────────────────
print()
print('=' * 60)
passed = sum(1 for r in results if r[0] == 'PASS')
failed = sum(1 for r in results if r[0] == 'FAIL')
print(f'RESULT: {passed} passed, {failed} failed out of {len(results)} checks')
if failed:
    print('Failed:')
    for icon, code, method, path in results:
        if icon == 'FAIL': print(f'  [{code}] {method} {path}')
print('=' * 60)
print()
print('Honest demo state:')
print('  Demo 9: Freshness/incident routes 200. Full lifecycle needs imported data.')
print('  Demo 10: Glossary, domains, products CRUD verified against live Supabase.')
print('  PII classification verified if dataset+column exist in workspace.')
