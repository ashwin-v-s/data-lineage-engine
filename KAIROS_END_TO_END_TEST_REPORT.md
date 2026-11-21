# KAIROS — End-to-End Test Report

Executed 2026-11-21 against:

- Deployed app: `https://data-lineage-engine-5i2x.vercel.app` (Vercel, frontend
  bundle `index-BI-DWeko.js` / `index--HCZZvnV.css`, `styles.neo.css?v=308`)
- Backend: the same Vercel Python function (`/api/*`, `/healthz`)
- Database: the shared Supabase Postgres project (PostgreSQL 17.6)
- Browser: Chromium via Playwright 1.65.1, 1440×950, real Supabase session
  injected into `localStorage` exactly as `auth.js` stores it

Test identity: the repository's documented test account
(`scripts/get_test_token.py`, `pranavsamal43@gmail.com`), workspace
`d91f7d80-dc3e-401e-9df4-e7670e4d3ba1`.

---

## 1. Suite results

| Suite | Command | Result |
| --- | --- | --- |
| Backend (pytest) | `python -m pytest -q` | **733 passed, 83 skipped, 0 failed** (16.9 s) |
| Frontend (vitest) | `npx vitest run` | **134 passed / 134** |
| Frontend build | `npm --prefix frontend run build` | **clean** (46 modules, 1.77 s) |
| Migration/table presence | `python scripts/db/verify_applied.py` | **PASS** — 44 tables, 0 missing columns, routines present |
| DB connectivity | `python scripts/test_connection.py` | **PASS** — PostgreSQL 17.6 |
| Deployed health | `GET /healthz`, `GET /api/v1/health` | **200**, `{"db":"ok"}` |

Skipped tests are the live/credential-gated ones (`KAIROS_LIVE_*` flags not set
for this run); their behaviour was exercised manually instead (section 3).

## 2. Authentication and tenancy

| Check | Expected | Actual | Verdict |
| --- | --- | --- | --- |
| Supabase password grant | 200 + session | 200, access token issued | PASS |
| Deployed API with bearer token | 200 | `/api/v1/me/workspaces` 200 | PASS |
| Workspace list shape | 1 workspace, role owner | `d91f7d80…`, `owner`, `current: true` | PASS |
| Browser session restore | dashboard visible, badge leaves CONNECTING | `LIVE` after ~14.6 s, 0 console errors | PASS |
| Cross-workspace isolation | not re-run here | prior evidence: `scripts/db/verify_workspace_isolation.py` PASS, 42 forced-RLS tables | NOT RUN THIS SESSION |
| 401 without token | 401 | API requires `require_user`; probes without a token are rejected | PASS (code + route guards) |

## 3. Ingestion pipeline (deployed API, real database)

| Step | Endpoint | Expected | Actual | Verdict |
| --- | --- | --- | --- | --- |
| Metadata graph preview | `POST /api/v1/ingest/preview` | 9 assets / 9 rel / 41 cols | exactly that, `commit_ready: true` | PASS |
| Metadata graph commit | `POST /api/v1/ingest/commit` | COMMITTED | `import_id cc782dcb…`, no warnings | PASS |
| SQL file preview/commit | same | 8 assets / 6 edges via SQLGlot | `2ac950e6…` | PASS |
| dbt manifest preview/commit | same | 8 assets / 8 edges | `b33f21f5…`, warning `UNRECOGNISED_DBT_MANIFEST_VERSION` (BUG-06) | PASS with warning |
| CSV headers preview/commit | same | 1 asset / 10 columns | `e958f1a0…`, `COMMITTED_WITH_WARNINGS` (no relationships) | PASS |
| File inventory preview/commit | same | file assets, no edges | 4 assets, `477e8d47…` | PASS |
| Idempotent replay | repeat metadata-graph commit | `replayed: true`, same id | exactly that | PASS |
| Catalog readback | `GET /api/v1/catalog` | committed assets + edges + evidence | 30 assets, 23 edges, 23 evidence | PASS |
| Persistence proof | direct SQL | rows in `dataset`/`lineage_edge`/`evidence` | 51 `column_record`, 5 `import_run`, matching edge counts | PASS |

## 4. Lineage, evidence and search

| Check | Expected | Actual | Verdict |
| --- | --- | --- | --- |
| Asset lineage | graph around the mart | 8 nodes / 8 edges | PASS |
| Capability registry | supported/available per tab | JSON with `supported/available/reason` | PASS |
| Edge evidence | stored evidence for the edge | rows returned for `5a9abd50…` | PASS |
| Downstream impact | bucketed depth levels | `customers` → `total_affected: 4` | PASS |
| Evidence as-of query | dated evidence | `included: 0`, 23 undated | **PARTIAL** (BUG-04) |
| Column lineage | column mappings | `total: 0` | **FAIL** (BUG-03) |
| Keyword search | results | `q=revenue` → 13 | PASS |
| 3D observatory | renders graph | 3,632 chars, 0 errors | PASS |

## 5. Governance, quality, freshness

| Check | Expected | Actual | Verdict |
| --- | --- | --- | --- |
| Create domain | 201 + row | 201 `f480e033…` | PASS |
| Create term + assign + approve | 201 + APPROVED | APPROVED `fce04495…`, assignment `created: true` | PASS |
| Create product with assets | 201 + links | `f33bea44…`, 2 assets | PASS |
| Dataset columns for PII | imported columns | **0 columns** for the `TABLE` duplicate | **FAIL** (BUG-01) |
| PII classification | 201 + readback | not created (no column id); endpoint contract validated | BLOCKED by BUG-01 |
| Quality assertion | 200/201 + row | `480a9715…` | PASS |
| Evaluate assertion | result row | PASS, checked 1, failed 0, `54a0cd91…` | PASS |
| Quality visible in UI | results on Data quality page + KPI | page says "No quality checks"; catalog returns `quality_checks: []` | **FAIL** (BUG-02) |
| Freshness SLA | 200 + row | 48/60/120 min `e0f15710…` | PASS |
| Freshness evaluation | status per SLA | `UNKNOWN` (no runtime signal) | PARTIAL (expected) |
| Incidents | lifecycle | 0 rows; page reads live API | PASS (empty state) |
| Notifications | rows on trigger | 0 rows; no trigger engine ran | PARTIAL |

## 6. Browser sweep (22 views, real session)

All views were loaded from the deployed app with a real Supabase session.
**0 console errors, 0 failed API requests** across the sweep. Rendered text and
screenshots are in `.demo-sources/visual/`.

| View | Load time | Result |
| --- | --- | --- |
| overview | ~14.6 s | LIVE badge, greeting, KPIs, catalog table |
| assets | 12.8 s | asset table with filters and CSV export |
| lineage | 12.0 s | graph + evidence-aware legend |
| evidence | 14.7 s | evidence list, four-state semantics |
| history | 15.9 s | bitemporal query form (empty dated set) |
| quality | 14.1 s | "No quality checks have been recorded yet" (BUG-02) |
| freshness | 17.6 s | SLA list and status legend |
| incidents | 14.4 s | live incident console, empty |
| glossary | 13.5 s | terms + link/approve forms |
| domains | 14.8 s | LIVE, `Finance & Revenue` row visible |
| products | 15.4 s | product + contract forms |
| notifications | — | empty, preference toggles |
| stewardship | — | request forms, empty |
| sources | — | PostgreSQL source form, 0 connections |
| integrations | — | GitHub connector status, API keys/webhooks |
| admin | 19.1 s | members, invite form, roles |
| settings | — | profile + preferences |
| search | 14.3 s | keyword search form |
| observatory | 16.8 s | 3D graph |

Load time is dominated by reloading `app.js` + `three.min.js` on every
`?view=` navigation; in-app navigation (clicking the sidebar) is much faster.
Presenters should navigate by clicking, not by editing the URL.

## 7. Defects

### BUG-01 — One logical dataset becomes 2–3 catalog assets (High, demo-blocking) — **READ SIDE FIXED, DEPLOYED**

The demo-blocking *symptom* is fixed (PR #15): the asset variant the UI opens may
carry no `column_record` rows, so `GET /governance/datasets/{id}/columns` and
`capabilities.schema` now fall back to the columns of the equivalent variant
(`workspace, name, namespace`), and `POST /governance/classifications` attaches a
classification to the asset that owns the column. Verified live: the SQL-file
variant of `customers` returns 6 columns, `capabilities.schema.available` is
true, and a `PII_SOURCE` classification was created on `customers.email` with
`dataset_id` resolved to the owning asset. Merging the duplicate rows is still
open and needs a migration plus a data decision.

`kairos_upsert_dataset` keys identity on
`(source_system, namespace, database_name, schema_name, name, asset_type)` and
each adapter assigns its own type (`table` from the metadata graph, `source`
from dbt sources, `model` from dbt models, `TABLE` from SQLGlot DDL). Result in
the demo workspace: 30 assets for 9 logical tables; `fct_daily_revenue` exists
as MODEL ×2 and TABLE; columns land on one variant while SQL-derived edges land
on another, so:

- `GET /api/v1/assets/{MODEL}/capabilities` → `schema.available = false`
  ("No columns have been imported") even though the same table has 6 columns;
- `GET /governance/datasets/{TABLE}/columns` → `[]`, so PII classification
  cannot be demonstrated on `customers.email`;
- lineage graphs show parallel duplicate nodes.

**Recommended fix:** normalise adapter asset types to a canonical kind
(`source|table|view|model|dashboard|file`) and add a reconciliation step keyed
on qualified name + namespace before upsert; or stop including `asset_type` in
the identity tuple and treat it as a mutable attribute. This needs a migration
and a backfill — do not hot-patch it before a demo.

**Demo workaround:** ingest only *one* adapter family per workspace. The
metadata graph alone yields 9 assets with 41 columns and 9 edges, and no
duplicates. SQL and dbt can be demonstrated in a second workspace.

### BUG-02 — Catalog hardcoded `quality_checks` and `column_classifications` (High, demo-blocking) — **FIXED, DEPLOYED AND VERIFIED**

`backend/app/api/routes/search.py:323-324`:

```python
"quality_checks": [],
"column_classifications": [],
"counts": {..., "quality_checks": 0, ...}
```

Quality results are stored (`quality_result` = 1 row, evaluated PASS) and PII
classifications are stored (`pii_classification`), but the catalog snapshot that
feeds Overview KPIs, the Data quality page and the PII overlay always receives
empty arrays. The Data quality page therefore prints *"Assertion creation and
stored quality results are not available in the backend yet"*, which is false.

**Fix applied locally (2026-11-21):** `catalog_snapshot` now loads the latest
`quality_result` per assertion via a `LATERAL` join and returns
`{id, rule_name, qualified_asset_name, dataset_id, check_type, severity, score,
status, checked_count, failed_count, evaluated_at}` with `score: null` (metadata
assertions are not scored, so the UI must not invent a number). It also returns
PII classifications joined to `column_record`/`dataset` with a derived
`is_pii` flag (`UNKNOWN` stays `null`). Both queries are guarded by
`to_regclass`, so a deployment without migration 0011 still serves the catalog
with empty arrays. Two new tests (`tests/test_catalog_governance_payload.py`)
pin the payload shape and the legacy-schema fallback; the existing catalog
limits test mock was extended for the new probe.

Verified: `pytest -q` → **735 passed, 83 skipped**; the SQL used by the route
returns the stored `PASS` result for `fct_daily_revenue` from the live database.

**Deployed 2026-11-21** (PR #14 → `4478a71`, `vercel deploy --prod`). Verified
against production:

- `GET /api/v1/catalog` now returns one `quality_checks` row for the demo
  workspace (`Revenue mart schema contract`, `fct_daily_revenue`, `schema`,
  `score: null`, `status: PASS`) and `counts.quality_checks: 1`.
- The Data quality page renders it end to end after a real form sign-in:
  **Recorded checks 1, Passed 1, Warnings 0, Failed 0**, with the table row
  `Revenue mart schema contract · fct_daily_revenue · schema · — · PASS ·
  21 Nov 2026, 17:06`. Screenshot `.demo-sources/visual/live-06-quality.png`.
- 0 console errors during the check.

**Remaining cosmetic issue:** with no scored checks the panel header prints
"Average score: 0.00" instead of "not scored" (`frontend/app.js`
`qualityPage()` computes the mean over an empty scored set). Not fixed yet.

### BUG-03 — Column-level lineage cannot be produced (High for the brief) — **NOT A QUERY BUG; DATA IS IN ANOTHER WORKSPACE**

Investigated 2026-11-21 after the demo deployment: the endpoint is correct. The
twelve COLUMN-granularity edges and their twelve column-level evidence rows
exist, but they belong to workspace `00000000-0000-4000-8000-000000000001` (the
seeded workspace), not to the demo account's workspace
`d91f7d80-dc3e-401e-9df4-e7670e4d3ba1`, whose 23 evidence rows are all
dataset-granularity. Under the workspace RLS the demo account therefore
genuinely has no column-level evidence, and `total: 0` is the honest answer.
To show column lineage in the demo workspace, column-level evidence has to be
produced *there* (static SQL analysis or OpenLineage ingest); no code change
will invent it.

Every adapter creates `granularity = 'DATASET'` evidence only. The metadata
graph contract has no column-endpoint fields, SQLGlot output is not expanded to
columns, and `/api/v1/column-lineage` reads COLUMN evidence, so it always
returns `{total: 0}`. The fixture README's claim of "rich column lineage" is not
backed by the stored data.

**Recommended fix:** extend the metadata-graph relationship contract with
`source_columns`/`target_columns` and emit COLUMN evidence (SQLGlot already
exposes column lineage in its qualifier output). Until then, present dataset
lineage and say column lineage is not yet implemented.

### BUG-04 — Static evidence is undated, so time travel returns nothing (Medium) — **BY DESIGN, NOT SILENT**

All 23 `edge_temporal_version` rows in the demo workspace carry
`effective_time_status = 'UNKNOWN'`, so `evidence-at-time` reports
`included: 0, undated_valid_time: 23` — it counts the undated rows instead of
pretending they were valid at the requested instant. Stamping an import time as
a business effective time would make the timeline look populated but wrong;
the fix is an ingest contract that records `event_time`/`effective_time` when a
source provides them. Edge travel itself works: every covered edge has a
`valid_from`.

`evidence.event_time` / `effective_time` are NULL for imports; the demo
workspace shows `included: 0, undated_valid_time: 23`. The bitemporal endpoint
is correct; the data has no timestamps. Use a runtime source or add an explicit
`effective_time` to the import contract.

### BUG-05 — Webhook URLs accept any HTTPS host (Low, security)

`backend/app/api/routes/webhooks.py:54-60` validates only the `https://` prefix
and the server then fetches that URL
(`backend/app/services/webhook_delivery.py:93-100`), storing 400 bytes of the
response. Add private/loopback/link-local/metadata blocking after DNS
resolution, or an allowlist.

### BUG-06 — dbt manifest version parser misses the canonical URL (Low) — **FIXED, DEPLOYED AND VERIFIED**

The parser now strips the `.json` suffix, so
`https://schemas.getdbt.com/dbt/manifest/v10.json` is recognised (pre-v7 URLs are
still rejected). Verified against production: previewing
`dbt_production_manifest.json` (schema URL `…/v10.json`) returns 8 assets, 8
relationships and **no warnings**; previously it emitted
`UNRECOGNISED_DBT_MANIFEST_VERSION`. New tests:
`test_m2b_json_suffixed_schema_url_is_accepted`,
`test_m2c_json_suffixed_pre_v7_url_is_rejected`.

A manifest declaring `"dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v10.json"`
imports successfully but warns `UNRECOGNISED_DBT_MANIFEST_VERSION`. The parser
expects a bare version token. Accept the `/v<N>.json` URL form.

### BUG-07 — Committed test credentials (Medium, security, carried from the audit) — **CODE FIXED, PASSWORD STILL MUST BE ROTATED**

`scripts/get_test_token.py` now reads `KAIROS_TEST_USER_EMAIL` /
`KAIROS_TEST_USER_PASSWORD` from the environment and exits with a clear message
when they are missing; no credential literal remains in the file. The value that
was already committed to history is still exposed, so it has to be rotated in
Supabase regardless of this change.

`scripts/get_test_token.py:39-40` contains a working account email and password
for the shared Supabase project. Rotate the password and read the values from
the environment. (This report used that account deliberately, as the only
available test identity; it is not reproduced in any deliverable.)

### BUG-08 — Slow first paint per URL navigation (Medium, demo risk)

Each `?view=` navigation reloads `app.js`, `three.min.js`, `chart.umd.min.js`
and refetches the catalog: 12–19 s to a stable page. Presenters must navigate
in-app. Longer-term: code-split the 3D/chart bundles and cache the catalog
snapshot per session.

## 8. What is still unverified, and why

| Area | Blocker |
| --- | --- |
| Two-real-user RLS proof through the browser | Needs a second account's credentials |
| `paranav` workspace catalogue depth | Only the test account's workspace is accessible |
| PostgreSQL source connect → sync | Needs a reachable source DB + `KAIROS_TOKEN_ENCRYPTION_KEY` |
| GitHub App import | Needs App credentials, installation, public callback |
| OpenLineage ingest | Needs `KAIROS_OPENLINEAGE_WEBHOOK_SECRET` + workspace binding on the deployment |
| Welcome / invitation email | Needs SMTP credentials and `KAIROS_PUBLIC_APP_URL` on Vercel |
| Scheduler-driven freshness, incidents, notifications | No scheduler is deployed; signals are `manual` |
| Hybrid vector search | No embeddings generated for this workspace |

## 9. Reproduction commands

```bash
python scripts/test_connection.py
python scripts/db/verify_applied.py
python -m pytest -q
npx vitest run
npm --prefix frontend run build
PLAYWRIGHT_BROWSERS_PATH=.pw-browsers node frontend/.demo-sweep.mjs   # local helper, git-ignored
```

All test rows created by this pass are retained deliberately (they are the demo
dataset) and are listed by id in `KAIROS_DEMO_DATA_CATALOG.md` §8 for cleanup.
