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
- [x] **PASS** PII classification — column fallback + classification ownership fixed and verified live (PR #15)
- [ ] **PARTIAL** Run records — 0 in the demo workspace, 2 globally
- [ ] **BLOCKED** Incidents and notifications — no scheduler/signal
- [ ] **BLOCKED** Column-level lineage — the column-level evidence lives in the seeded workspace, not this one (BUG-03)
- [ ] **PARTIAL** Dated/temporal evidence — undated rows are counted, not silently excluded (BUG-04)

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

- [x] **PASS** Data quality panel — 1 recorded check, 1 PASS rendered live (BUG-02 fixed)
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
| BUG-02 | `catalog` hardcoded `quality_checks: []` and `column_classifications: []` | **Fixed, deployed, verified live** (PR #14) — 1 recorded check, PASS, and no fake 0.00 average |
| BUG-03 | Demo workspace has no COLUMN-granularity evidence (the 12 column edges are in the seeded workspace) | Produce column evidence in the demo workspace (SQLGlot / OpenLineage); no query fix exists |
| BUG-06 | dbt v10 schema URL warns `UNRECOGNISED_DBT_MANIFEST_VERSION` | **Fixed, deployed** — `…/v10.json` parses with 0 warnings |
| BUG-07 | Committed test credentials in `scripts/get_test_token.py` | **Code fixed** (env-only); the exposed password still needs rotating in Supabase |
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
| Quality and PII demos | ✅ working (BUG-02/01 symptom fixed); temporal demo is partial (BUG-04) |
| External integrations | ⛔ blocked on credentials |
| Documentation (6 deliverables) | ✅ |

## 2026-11-22 — merged M4 branch and audit fixes (code state)

- Pulled `origin/codex/m4-gauree-completion` into `main`. It was the only branch
  ahead of `main`; both remotes' `main` branches were already fully fetched.
- New in this build: service-backed OpenLineage ingest with `/ingest/openlineage/preview`,
  coverage-aware `/assets/{id}/downstream-impact`, the column-lineage scope fix,
  membership-safe workspace reads, the edge evidence inspector (aggregate vs.
  stored record), refresh-catalog on the lineage page, and per-run asset/event counts
  computed from stored evidence and raw events.
- Conflict rule applied: keep the newer implementation per feature, not one side
  wholesale. Ingest takes the branch's service for events plus main's static-import
  commit path; workspace routes keep main's `/me/workspaces` and welcome-email
  endpoints; `app.js` keeps main's UI and adds only the branch's new panels.
- OpenLineage producers accept either a signed-in session / Kairos API key or the
  server-side `KAIROS_OPENLINEAGE_WEBHOOK_SECRET` scoped to
  `KAIROS_OPENLINEAGE_WORKSPACE_ID`; the secret is ignored unless both are set.
- Fixed in this pass: hybrid search returning 403 for every session; viewer access to
  metadata and source mutations; lineage dependency 500s (now 404/422); database
  exception text in `/api/v1/health`; hardcoded zero run counts; four tables missing
  from the RLS verifier; migration range pinned at 0017.
- Verified this pass: backend `816 passed, 83 skipped`; frontend `155 passed`;
  production build clean; `check_migrations.py` PASS (0017, 0 gaps);
  `verify_applied.py` PASS (44 tables); `verify_rls.py` PASS (47/47);
  app boots locally (`/healthz` 200, `/` 200, 122 documented API paths).
- Still blocked on credentials or infrastructure, not code: SMTP, GitHub App,
  a reachable PostgreSQL source, embeddings for vector search, a scheduler for
  freshness/incidents/notifications, and a second real user for the isolation demo.
- The deployed site served commit `e398cd0` until 2026-11-22; the go-ahead was
  given and `main` is now published (see the deployment section below).

## 2026-11-22 — production deployment (done)

- `vercel --prod` from `main` @ `75c360c` (CLI 65.9.0, account `jat-in32006`).
  Deployment `3WQdi955cMcDHfUpVEVzBBJL1SFe`, aliased to
  `https://data-lineage-engine-5i2x.vercel.app`.
- Live verification on the aliased domain:
  - `/healthz` → `200 {"status":"ok","service":"kairos-api"}`
  - `/` → `200 text/html; charset=utf-8`
  - `/api/v1/auth/config` → `200` with Supabase URL + publishable key
  - `/api/v1/catalog` → `401 {"error":{"code":"UNAUTHENTICATED",...}}` (fail-closed)
  - `/ingestion.html` → `302 /?signin_required=1` (no raw JSON to a browser)
- Re-verified against the live database the same day: `verify_applied.py` PASS,
  `verify_rls.py` **47/47** PASS, `verify_workspace_isolation.py` PASS,
  `check_migrations.py` PASS (0017, 0 gaps).
- Suite state at deploy time: backend **816 passed, 83 skipped**; frontend
  **155 passed** (14 files); 3 Playwright specs; OpenAPI **122 paths**, 0 drift.
- M1 handout (`docs/handouts/M1_JATIN_platform_identity_deployment.md`) now
  carries the deployed commit, deployment ID and the live evidence block.
  `docs/DEMO_1_SIGNIN_WORKSPACE_ISOLATION.md` preflight counts were corrected
  from 15 migrations / 44 tables / 43 RLS tables to the real 17 / 47 / 47, and
  its auth-surface claim now matches the measured 134-of-139 protected operations.
- Remaining demo risk (unchanged, no code fix): the two-user browser isolation
  walkthrough still needs two provisioned Supabase accounts; the DB/RLS and API
  scoping proofs already pass. GitHub App, embeddings key and the scheduler
  remain blocked on credentials/decision, not on M1 code.

## 2026-11-22 — demo flows verified against the deployed site

Signed in to production with the configured demo account (never printed) and exercised
the demo paths over HTTPS, not localhost:

- **Demo 1 prerequisites:** `/api/v1/me/workspace` `200`, `/api/v1/me/workspaces` `200`
  (role `owner`), `/api/v1/catalog` `200` with 30 assets, asset detail + lineage +
  capabilities `200`, audit trail `200`, governance `terms`/`domains`/`products` `200`
  with real rows.
- **Demo 3 prerequisites:** fixture verifier 5/5 PASS; ingestion subset **71 passed**;
  `POST /api/v1/ingest/preview` on the enterprise metadata graph returns
  `9 assets / 9 relationships / 41 columns / 0 warnings / writes: 0`; `/api/v1/ingest/runs`
  shows the earlier upload run. Nothing was written to production data.
- **Fail-closed still holds live:** `/api/v1/catalog` without a token `401`,
  `/ingestion.html` `302 → /?signin_required=1`.

Still a human step, not a code gap: the second-account browser isolation walkthrough
from Demo 1 step 6–7.
