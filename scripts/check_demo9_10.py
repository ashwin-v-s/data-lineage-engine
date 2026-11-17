"""Check demo 9 and 10 routes against live deployed URL and local app."""
import os, sys
from dotenv import load_dotenv
load_dotenv('.env')
import httpx

# Get token
SUPABASE_URL = os.getenv('SUPABASE_URL', '').rstrip('/')
ANON_KEY = os.getenv('SUPABASE_PUBLISHABLE_KEY', '')
headers_sb = {'apikey': ANON_KEY, 'Content-Type': 'application/json'}
resp = httpx.post(
    f'{SUPABASE_URL}/auth/v1/token?grant_type=password',
    headers=headers_sb,
    json={'email': 'pranavsamal43@gmail.com', 'password': 'Kairos_Test_2026!'},
    timeout=15
)
if resp.status_code != 200:
    print('Login failed:', resp.json()); sys.exit(1)
TOKEN = resp.json()['access_token']
print(f'Logged in: pranavsamal43@gmail.com\n')

BASE = 'https://data-lineage-engine-mu.vercel.app'
auth = {'Authorization': f'Bearer {TOKEN}'}

def test(method, path, desc, body=None):
    if method == 'GET':
        r = httpx.get(f'{BASE}{path}', headers=auth, timeout=15)
    else:
        r = httpx.post(f'{BASE}{path}', headers=auth, json=body or {}, timeout=15)
    status = r.status_code
    icon = 'OK' if status < 300 else 'FAIL'
    print(f'  [{icon} {status}] {method} {path}')
    print(f'          {desc}')
    if status == 200:
        try:
            b = r.json()
            if isinstance(b, dict):
                print(f'          Response keys: {list(b.keys())[:5]}')
                # show counts if available
                for k in ['count','total','slas','incidents','evaluations','terms','domains','products']:
                    if k in b:
                        v = b[k]
                        if isinstance(v, list):
                            print(f'          {k}: {len(v)} items')
                        else:
                            print(f'          {k}: {v}')
        except: pass
    return status

# ── Demo 9: Freshness, Quality, Incident lifecycle ───────────────────────────
print('=' * 60)
print('DEMO 9 — Freshness, Quality, Incident lifecycle')
print('=' * 60)
test('GET', '/api/v1/governance/slas',                  'List all freshness SLAs in workspace')
test('GET', '/api/v1/governance/freshness',              'Freshness evaluation status')
test('GET', '/api/v1/governance/incidents',              'List all incidents')
test('POST', '/api/v1/governance/slas',                  'Create a freshness SLA',
     body={"dataset_id": "00000000-0000-0000-0000-000000000001",
            "max_staleness_hours": 24, "schedule_cron": "0 * * * *",
            "severity": "warning"})
test('GET', '/api/v1/governance/freshness',              'Re-check freshness after SLA create')

# Check quality routes
from backend.app.main import app
all_routes = sorted([r.path for r in app.routes if hasattr(r, 'path') and '/api/' in r.path])
quality_routes = [r for r in all_routes if 'quality' in r or 'assertion' in r]
print(f'\n  Quality routes in app: {quality_routes if quality_routes else "none — quality not yet wired"}')

notification_routes = [r for r in all_routes if 'notif' in r]
print(f'  Notification routes: {notification_routes if notification_routes else "none"}')

# ── Demo 10: Glossary, PII, Domains, Products ────────────────────────────────
print()
print('=' * 60)
print('DEMO 10 — Glossary, PII, Domains, Data Products')
print('=' * 60)

# Find what governance/glossary routes exist
gov_routes = [r for r in all_routes if any(x in r for x in
    ['glossary','domain','product','classif','pii','term','contract'])]
if gov_routes:
    print('  Routes found:')
    for r in gov_routes:
        test('GET', r, f'Test {r}')
else:
    print('  No glossary/domain/product routes in current app')
    print('  Checking governance registry...')
    gov_reg = [r for r in all_routes if 'governance' in r]
    print(f'  Governance routes: {gov_reg}')
    for r in gov_reg:
        test('GET', r, f'{r}')

# Try governance registry (M4 added this)
test('GET', '/api/v1/governance/slas',   'Governance SLAs (workspace governance)')
test('GET', '/api/v1/governance/incidents', 'Governance incidents')
