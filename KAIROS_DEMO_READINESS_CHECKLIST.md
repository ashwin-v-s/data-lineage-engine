# KAIROS — Demo Readiness Checklist

Date: 2026-11-21. Legend: **VERIFIED** = executed and read back this session;
**PARTIAL** = works with a stated gap; **BLOCKED** = needs credentials or
infrastructure; **UNVERIFIED** = not executed.

## Environment

- [x] **VERIFIED** Deployed app reachable (`/` 200, `/healthz` 200, `/api/v1/health` db ok)
- [x] **VERIFIED** Frontend bundle is the current build (`index-BI-DWeko.js`, `index--HCZZvnV.css`)
- [x] **VERIFIED** Database reachable (PostgreSQL 17.6)
- [x] **VERIFIED** 44 tracked tables/columns/routines present (`verify_applied.py`)
- [x] **VERIFIED** Backend suite 733 passed / 83 skipped
- [x] **VERIFIED** Frontend suite 134 passed
- [x] **VERIFIED** Production build clean
- [ ] **BLOCKED** SMTP credentials for invitation/welcome email
- [ ] **BLOCKED** `KAIROS_TOKEN_ENCRYPTION_KEY` + a reachable PG source
- [ ] **BLOCKED** GitHub App credentials + installation
- [ ] **BLOCKED** `KAIROS_OPENLINEAGE_WEBHOOK_SECRET` + workspace binding
- [ ] **UNVERIFIED** Second real user for a two-account isolation demo

## Demonstration data

- [x] **VERIFIED** Enterprise metadata graph committed (9 assets, 9 edges, 41 columns; `cc782dcb…`)
- [x] **VERIFIED** SQL pipeline committed (8 assets, 6 edges; `2ac950e6…`)
- [x] **VERIFIED** dbt manifest committed (8 assets, 8 edges; `b33f21f5…`)
- [x] **VERIFIED** CSV schema committed (1 asset, 10 columns; `e958f1a0…`)
- [x] **VERIFIED** File inventory committed (4 assets; `477e8d47…`)
- [x] **VERIFIED** Idempotent replay returns the same import id
- [x] **VERIFIED** Domain, term (APPROVED), term↔asset link, product with 2 assets
- [x] **VERIFIED** Quality assertion + PASS result
- [x] **VERIFIED** Freshness SLA (48/60/120 min)
- [x] **VERIFIED** Catalog readback: 30 assets / 23 edges / 23 evidence
- [ ] **PARTIAL** PII classification — blocked by duplicate-asset columns (BUG-01)
- [ ] **PARTIAL** Run records — 0 in the demo workspace, 2 globally
- [ ] **BLOCKED** Incidents and notifications — no scheduler/signal
- [ ] **BLOCKED** Column-level lineage — adapter gap (BUG-03)
- [ ] **PARTIAL** Dated/temporal evidence — imports are undated (BUG-04)

## Features — presentable now

- [x] **VERIFIED** Sign-in, session restore, workspace switcher
- [x] **VERIFIED** Overview KPIs and asset table
- [x] **VERIFIED** All assets, filters, CSV export
- [x] **VERIFIED** Asset profile and capability registry
- [x] **VERIFIED** Catalog structure
- [x] **VERIFIED** Ingestion preview/commit/idempotency (API and UI path)
- [x] **VERIFIED** Lineage explorer (2D), edge evidence, downstream impact
- [x] **VERIFIED** Evidence & reasoning (four states)
- [x] **VERIFIED** Domains, glossary, data products (API + UI rows)
- [x] **VERIFIED** Freshness SLA storage and status semantics
- [x] **VERIFIED** Workspace administration (members, roles, invites UI)
- [x] **VERIFIED** Catalog keyword search (13 hits for "revenue")
- [x] **VERIFIED** 3D observatory
- [x] **VERIFIED** Preference and profile screens
- [x] **VERIFIED** Zero console errors / zero failed API calls across 22 views

## Features — present with the stated caveat

- [ ] **PARTIAL** Data quality panel — prove via API/DB, panel is blind (BUG-02)
- [ ] **PARTIAL** PII classification — use a dataset variant that has columns
- [ ] **PARTIAL** Time travel — mechanism only, empty dated set
- [ ] **PARTIAL** Lineage graph — duplicate nodes must be explained (BUG-01)
- [ ] **PARTIAL** Notifications — empty state only, preferences work
- [ ] **PARTIAL** Incidents — empty state only
- [ ] **PARTIAL** Sources — form only, no connection
- [ ] **PARTIAL** Integrations — GitHub shows not configured
- [ ] **PARTIAL** Hybrid/vector search — route present, no embeddings

## Demo-blocking defects (fix before claiming completeness)

| # | Defect | Owner action |
| --- | --- | --- |
| BUG-01 | One dataset becomes 2–3 assets; columns/edges split | Normalise adapter asset types + reconcile on qualified name (migration + backfill) |
| BUG-02 | `catalog` hardcoded `quality_checks: []` and `column_classifications: []` (`search.py:323-324`) | **Fixed locally** — queries + `to_regclass` guard + 2 tests; 735 backend tests pass. Needs deploy approval |
| BUG-03 | No COLUMN-granularity evidence anywhere | Extend import contract + SQLGlot column mapping |
| BUG-06 | dbt v10 schema URL warns `UNRECOGNISED_DBT_MANIFEST_VERSION` | Accept `/v<N>.json` form |
| BUG-07 | Committed test credentials in `scripts/get_test_token.py` | Rotate; read from environment |
| BUG-08 | 12–19 s per URL navigation | Click navigation in demos; split 3D/chart bundles later |

## Presenter readiness

- [x] **VERIFIED** Demo credentials stored in the git-ignored `.env` as `KAIROS_DEMO_EMAIL` / `KAIROS_DEMO_PASSWORD`
- [x] **VERIFIED** Real login through the Stitch sign-in form (not just token injection): dashboard reached LIVE in 10.4 s, session written by `auth.js`, 0 console errors, 0 failed API calls
- [ ] Demo workspace selected (Personal workspace `d91f7d80…`)
- [ ] Badge shows LIVE before speaking
- [ ] Fixtures folder open in the file manager
- [ ] `KAIROS_COMPLETE_DEMO_GUIDE.md` open on a second screen
- [ ] API tab ready (`/docs` or a saved `curl` for `/api/v1/catalog`)
- [ ] One-sentence disclosure ready: "This is synthetic demonstration data modelling a revenue analytics stack."

## Sign-off

| Area | Status |
| --- | --- |
| Application runs against real auth + DB | ✅ |
| Demonstration data prepared and traceable | ✅ |
| Core workflow (ingest → catalog → lineage → evidence → governance) executed | ✅ |
| Quality, PII and temporal demos | ⚠️ partial (BUG-01/02/04) |
| External integrations | ⛔ blocked on credentials |
| Documentation (6 deliverables) | ✅ |
