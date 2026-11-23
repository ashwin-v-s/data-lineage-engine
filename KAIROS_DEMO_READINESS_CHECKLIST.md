# KAIROS — Demo Readiness Checklist

Date: 2026-11-21. Legend: **VERIFIED** = executed and read back this session;
**PARTIAL** = works with a stated gap; **BLOCKED** = needs credentials or
infrastructure; **UNVERIFIED** = not executed.

## Environment

- [x] **VERIFIED** Deployed app reachable (`/` 200, `/healthz` 200, `/api/v1/health` db ok)
- [x] **VERIFIED** Frontend bundle is the current build (`index-BI-DWeko.js`, `index--HCZZvnV.css`)
- [x] **VERIFIED** Database reachable (PostgreSQL 17.6)
- [x] **VERIFIED** 44 tracked tables/columns/routines present (`verify_applied.py`)
- [x] **VERIFIED** Backend suite 843 passed / 83 skipped
- [x] **VERIFIED** Frontend suite 156 passed
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
- [x] **VERIFIED** Catalog readback after identity reconciliation: 17 active assets / 42 edges (23 dataset + 19 column) / 42 evidence rows / 1 quality check
- [x] **PASS** PII classification — column fallback + classification ownership fixed and verified live (PR #15)
- [ ] **PARTIAL** Run records — 0 in the demo workspace, 2 globally
- [ ] **BLOCKED** Incidents and notifications — no scheduler/signal
- [x] **PASS** Column-level lineage — SQLGlot projections emitted 19 COLUMN evidence rows and edges in this workspace (BUG-03 fixed)
- [x] **PASS** Dated/temporal evidence — the dbt manifest's source-declared `generated_at` gives 8 dependencies a KNOWN valid interval; the remaining 34 undated rows are counted, not silently excluded (BUG-04 limited to sources without a timestamp)

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
- [x] **PASS** PII classification — one classification resolves to the merged `customers` asset and its column
- [x] **PASS** Time travel — 8 dated dbt dependencies at today, 0 before 2026-11-16, 8 from 2026-11-18; 34 undated records reported separately
- [x] **PASS** Lineage graph — one row per logical dataset; only genuinely different kinds (table/dashboard/exposure) share a name (BUG-01 fixed)
- [ ] **PARTIAL** Notifications — empty state only, preferences work
- [ ] **PARTIAL** Incidents — empty state only
- [ ] **PARTIAL** Sources — form only, no connection
- [ ] **PARTIAL** Integrations — GitHub shows not configured
- [ ] **PARTIAL** Hybrid/vector search — route present, no embeddings

## Demo-blocking defects (fix before claiming completeness)

| # | Defect | Owner action |
| --- | --- | --- |
| BUG-01 | One dataset becomes 2–3 assets; columns/edges split | **Fixed** — migration 0018 canonical identity + merge; adapters write declared schema; demo merged 30 → 17 |
| BUG-02 | `catalog` hardcoded `quality_checks: []` and `column_classifications: []` | **Fixed, deployed, verified live** (PR #14) — 1 recorded check, PASS, and no fake 0.00 average |
| BUG-03 | Demo workspace has no COLUMN-granularity evidence | **Fixed** — SQL file adapter emits column projections; 19 mappings backfilled and confirmed through the API query |
| BUG-06 | dbt v10 schema URL warns `UNRECOGNISED_DBT_MANIFEST_VERSION` | **Fixed, deployed** — `…/v10.json` parses with 0 warnings |
| BUG-07 | Committed test credentials in `scripts/get_test_token.py` | **Code fixed** (env-only); the exposed password still needs rotating in Supabase |
| BUG-05 | Webhook URLs accepted any HTTPS host | **Fixed** — literal private hosts rejected at registration and DNS re-checked at delivery (tests cover both) |
| BUG-08 | 12–19 s per URL navigation | **Fixed** — `three.min.js` (670 KB) and `observatory.js` now load only when the 3D view opens |

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
| Quality, PII, column-lineage and time-travel demos | ✅ working (BUG-01/02/03 fixed; dbt gives 8 dated dependencies, other undated evidence is counted) |
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
  (role `owner`), `/api/v1/catalog` `200` with 30 assets (before migration 0018;
  now 17), asset detail + lineage +
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

## 2026-11-22 — credential-free completion pass

Everything that did not need another person's account was finished, tested and
deployed:

- **Semantic search unblocked one layer.** Migration `0012` applied to the live
  database (vector 0.8.2, `dataset.embedding`, ivfflat cosine index);
  `openai>=1,<2` added to `requirements.txt`; `scripts/backfill_embeddings.py`
  added (`--dry-run` reports **122 datasets without an embedding**). The search
  endpoint now refuses to imply vector ranking: it exposes `mode` + `note`,
  returns `503` for explicit semantic requests without a key, and serves keyword
  results for `mode=hybrid` until embeddings exist.
- **Signed OpenLineage webhooks are functional in production.**
  `KAIROS_WEBHOOK_SIGNING_SECRET` and `KAIROS_OPENLINEAGE_WORKSPACE_ID` were
  generated/set on the Vercel production environment; `X-Kairos-Signature`
  HMAC-SHA256 over the raw body is verified in constant time, invalid signatures
  are `401`, and a replay by `runId` still commits once.
- **Honesty gate in CI.** `scripts/check_ui_claims.py` fails the build when a
  live view requests an endpoint the OpenAPI contract does not expose (15 request
  paths checked, currently PASS). Coverage floor raised from 40% to **45%**
  (actual 62.88%).
- **Adapter inventory corrected.** `ingestion/ADAPTER_STATUS.md` no longer claims
  the metadata-graph, dbt, inventory and CSV adapters lack API wiring.
- Verification this pass: **822 passed / 83 skipped**, coverage gate PASS,
  **155** vitest, 14 e2e specs → 7 passed / 1 skipped, OpenAPI 122 paths with 0
  drift after regenerating the snapshot, migrations PASS (0017, 0 gaps),
  `verify_applied` PASS, `verify_rls` **47/47** PASS, production build clean.
- Still blocked on credentials or decisions, not code: `OPENAI_API_KEY` for the
  embedding backfill, GitHub App secrets, a scheduler location (D12), and a
  second Supabase account for the two-user isolation walkthrough.

## 2026-11-22 — defect pass found by auditing the running product

- **False operational claim fixed in source sync.** `/sources/{id}/sync` recorded
  `assets_created = <all discovered assets>` on every run, so the new sync-history
  view would have reported every re-synced table as newly created. The route now
  checks each asset's identity before upserting and records `assets_created` vs
  `assets_updated` (re-synced existing) separately, leaving `assets_unchanged`
  NULL because field-level diffs are not tracked. The SQL was validated against
  the live schema in a rolled-back transaction.
- **Sync history is now visible.** The Sources screen reads
  `GET /api/v1/sources/{id}/runs?limit=5` for each configured source and renders
  one row per run (status, start, duration, discovered, new, existing, failed,
  error). A source with no runs says so instead of showing zeros.
- **Database error text no longer reaches clients.** OpenLineage ingest wrapped
  `{exc}` into its 503 body; it now logs the driver message with the request id
  and returns a stable message.
- **Semantic readiness check is a short-circuit.** `EXISTS (... LIMIT 1)` instead
  of `COUNT(*)` over `dataset`, so hybrid requests do not scan the table.
- **OpenAPI snapshots reconciled.** `docs/openapi.json` (the exported artifact)
  and `contracts/api/openapi.json` both hold 122 identical paths; drift check
  reports 0.
- **Living-doc numbers corrected:** 44→47 tables in `KAIROS_FEATURE_INVENTORY.md`
  and `KAIROS_END_TO_END_TEST_REPORT.md`, 43→47 RLS tables in
  `docs/CHATGPT_SYSTEM_CONTEXT_PROMPT.md`; the pasted output in
  `docs/M1_SIGNUP_PROOF.md` is annotated as-of rather than rewritten.
- **M3 handout corrected:** the asset profile already ships Activity and
  Relationships tabs (`assetProfile()` in `app.js`); the handout now says so
  instead of asking for them to be built.
- Verification: **822 passed / 83 skipped**, coverage **62.80%** (gate 45%),
  **155** vitest, production build clean, migrations PASS, RLS **47/47** PASS,
  UI claim gate PASS.
