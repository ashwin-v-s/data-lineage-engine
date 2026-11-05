# Kairos — Executed Verification Report (not a status summary)

**Date:** 2026-11-02 · **Tree:** `feature/product-completion` @ `a0621f2` (working tree, uncommitted surface included)
**Method:** every row below is something I **ran today on this machine**, with the command and its real output. Nothing here is inferred from a PR description, a migration header, a doc claim, or a test name. Where a suite is green, I also state what it does *not* prove.

**Why this file exists:** the project's own rule is "never write 'it works' unless you ran it". Four of the five members' status claims could not survive that rule when tested. This is the measurement, and [handouts/](handouts/README.md) §"Not working — verified" assigns each defect to a named owner.

---

## 1. Backend test suite — green, and misleading

| Command | Result | What it actually proves |
|---|---|---|
| `python -m pytest -q` | **346 passed, 80 skipped, 0 failed** (6.3 s) | pure logic layers: SQL parsers, normalizers, schemas, `services/freshness.py` (100 %), `token_crypto` (92 %), `github_app` (71 %) |
| `KAIROS_LIVE_API_TESTS=1 python -m pytest -q` | **346 passed, 80 skipped** — byte-identical | **the documented opt-in flag does nothing.** The real gate is `KAIROS_TEST_USER_TOKEN` |
| `python -m pytest -q -rs` (skip reasons) | 76 × *"Set `KAIROS_TEST_USER_TOKEN` to a valid Supabase end-user access token"*, 2 × LEFT/RIGHT JOIN unreliable | Gate 1 (workspace isolation) and Gate 2 (idempotent commit) **have never been executed by anyone** |

`docs/PROJECT_STATUS_2026-11-02.md` §2 and the CI docs both name `KAIROS_LIVE_API_TESTS`; the code names `KAIROS_TEST_USER_TOKEN` ([test_live_api.py:57](file:///E:/EDI-Metadata_Lineage/tests/test_live_api.py#L57), [test_ingest_runs.py:59](file:///E:/EDI-Metadata_Lineage/tests/test_ingest_runs.py#L59)). The flag in the docs is not the flag in the code.

### Function-level coverage — the real answer to "is it tested"

`python -m pytest --cov=backend.app --cov-report=term-missing` → **TOTAL 40 %** (3813 statements, 2280 missed).

| Module | Coverage | Untested range |
|---|---|---|
| [audit.py](file:///E:/EDI-Metadata_Lineage/backend/app/api/routes/audit.py) | **9 %** | 453 of 498 statements — versions, diff, rollback, compliance-report, export |
| [lineage.py](file:///E:/EDI-Metadata_Lineage/backend/app/api/routes/lineage.py) | **15 %** | 140 of 165 |
| [owner.py](file:///E:/EDI-Metadata_Lineage/backend/app/api/routes/owner.py) | **15 %** | 159 of 186 |
| [metadata.py](file:///E:/EDI-Metadata_Lineage/backend/app/api/routes/metadata.py) | **16 %** | 111 of 132 |
| [search.py](file:///E:/EDI-Metadata_Lineage/backend/app/api/routes/search.py) | **18 %** | 67 of 82 |
| [governance.py](file:///E:/EDI-Metadata_Lineage/backend/app/api/routes/governance.py) | **28 %** | 135 of 187 |
| [ingest.py](file:///E:/EDI-Metadata_Lineage/backend/app/api/routes/ingest.py) | **28 %** | 79 of 109 — commit path 135-267 entirely untested |
| [sources.py](file:///E:/EDI-Metadata_Lineage/backend/app/api/routes/sources.py) | **31 %** | 133 of 193 — wizard steps 324-427 untested |
| [dependency.py](file:///E:/EDI-Metadata_Lineage/backend/app/api/routes/dependency.py) | 36 % | 86 of 134 |
| [assets.py](file:///E:/EDI-Metadata_Lineage/backend/app/api/routes/assets.py) | 50 % | 12 of 24 |
| [capabilities.py](file:///E:/EDI-Metadata_Lineage/backend/app/api/routes/capabilities.py) | 67 % | 21 of 64 |
| [integrations.py](file:///E:/EDI-Metadata_Lineage/backend/app/api/routes/integrations.py) | 89 % | 12 of 110 |
| `backend/app/mock_repo.py` | **0 %** | 135 statements |
| `backend/app/repositories/` (base + mock_repository) | **0 %** | 227 statements — an entire data layer no test or route imports |
| `backend/app/schemas.py` (legacy single-file) | **0 %** | 153 statements |

Per-endpoint body coverage, computed from the coverage JSON against `@router.*` functions: **70 endpoint handlers, 64 with zero body lines executed, 65 below 50 %.** The handlers are *entered* (FastAPI validates the request, then auth rejects it) and their logic never runs.

The clearest example is the suite people cite as proof the incident lifecycle works — [tests/test_incidents.py:6](file:///E:/EDI-Metadata_Lineage/tests/test_incidents.py#L6) states its own limit: *"assert only the pure request-validation behaviour"*, and all seven HTTP tests assert `status_code == 422`. **No test creates an SLA, acknowledges an incident, or resolves one.**

### 1b. The rest of the tree — and what genuinely *is* tested

`--cov=backend.app` above covered only the API package. The ingestion engine and the research track live at the repo root, so I measured them separately (`python -m pytest --cov=ingestion --cov=research --cov=scripts`):

| Area | Module | Coverage | Read |
|---|---|---|---|
| **Research** | `research/reasoning/engine.py` | **96 %** | the four-state engine is real and exercised |
| | `research/metrics/metrics.py`, `missingness/mcar.py`, `missingness/capture_manifest.py` | **100 %** | metrics + missingness injection genuinely run |
| | `research/baselines/baselines.py`, `experiments/protocol_loader.py` | **98 %** | baselines and protocol loading genuinely run |
| | `research/ground_truth/provider.py` / `provsql_provider.py` / `reference_interpreter.py` | 94 / 100 / 100 % | *executed* — but see §8 on whether they compute or delegate |
| **Ingestion** | `ingestion/openlineage/normalizer.py` | **81 %** | dedupe, retry, out-of-order and *"missing events do not create negative evidence"* are each asserted by a test ([test_runtime_normalizer.py:30-100](file:///E:/EDI-Metadata_Lineage/tests/test_runtime_normalizer.py#L30)) |
| | `ingestion/sql/__init__.py` | 83 % | the SQL parser path is exercised |
| | `ingestion/metadata_graph/__init__.py` | 77 % | fixture-import adapter exercised |
| | `ingestion/postgres_source.py` | 81 % | exercised offline |
| | **`ingestion/dbt/manifest.py`** | **7 %** (161 of 174 missed) | **the dbt adapter is essentially unexecuted** — any "dbt works" claim is unsupported |
| | `ingestion/static_files/inventory.py` / `csv_headers.py` | **12 % / 18 %** | the file-upload evidence paths are unexecuted |
| | `ingestion/openlineage/load_*.py`, `process_runtime_events.py`, `etl_demo.py`, `sql/b1_adapter.py` | **0 %** | five scripts nothing runs — including the event loaders the demo would need |
| **Tooling** | `scripts/check_deployment.py` | 0 % | the deployment gate has no test of its own |

So the honest shape of the project is **not** "untested": the *reasoning and parsing cores are well covered* (31 tests pass in `test_runtime_normalizer.py` + `test_engine_rules.py` + `test_static_unsupported.py`, 2 skipped for known LEFT/RIGHT JOIN weakness), while the **API bodies, the connectors' adapters (dbt, files), and every UI data path are unexecuted**. That is a different problem from "no tests", and it needs a different fix.

## 2. Live route probe — 66 of 68 routes are unreachable

Started the real server (`python -m uvicorn backend.app.main:app --port 8000`) and requested **every** path in the served OpenAPI document with substituted IDs and `{}` bodies.

| Outcome | Count | Routes |
|---|---|---|
| `200` | **2** | `/healthz`, `/api/v1/auth/config` |
| `401 UNAUTHENTICATED` | **66** | every catalog, lineage, search, evidence, ingest, sources, governance, audit, owner, metadata, personalization, integrations, rea route |
| `500` / `503` / panic | **0** | none — no route crashed on request shape |

Security verdict: **correct and fail-closed** ([auth.py:23-68](file:///E:/EDI-Metadata_Lineage/backend/app/auth.py#L23-L68) validates against Supabase `/auth/v1/user` and provisions the workspace server-side; `auth_disabled()` hard-returns `False`).
Product verdict: **nothing behind the wall has ever been exercised**, because [auth.py:56](file:///E:/EDI-Metadata_Lineage/backend/app/auth.py#L56) needs a live DB and the token gate needs a real signed-up user. `require_user` cannot be satisfied by a hand-made JWT — it calls the hosted Auth service, so there is no local dev path.

## 3. Routes the plan requires that do not exist at all

Checked against the served OpenAPI path list (67 paths):

| Required by | Capability | Present? |
|---|---|---|
| Perplexity §6 / v2 §9 / M2 item 5 | `POST /ingest/openlineage` push receiver | **NO** |
| M2 item 6 | `GET /sources/{id}/runs` sync history | **NO** |
| M2 item 6 | `GET /sources/health` rollup | **NO** |
| Spec §8 / M4 task 8 | quality assertions + results | **NO** |
| Spec §11 / M4 task 9 | glossary terms, term assignment | **NO** |
| M4 task 10 | domains, data products, data contracts | **NO** |
| Spec §13 / M4 task 11 | notifications | **NO** |
| M4 task 12 | workspace members/roles admin, API keys, webhook registration | **NO** (only `/owner/team-members`) |
| Spec §7 | vector/hybrid search | **NO** (keyword `/search` only) |
| Spec §11 | PII classification records | **NO** |

Present and plausible: `/evidence-at-time` (time travel), `/column-lineage`, `/assets/{id}/downstream-impact`, `/ingest/preview|commit|runs`, `/sources` CRUD + `/test|preview|sync`, `/governance/*` (SLA, freshness, evaluate, incidents + ack/investigate/resolve), `/capabilities`.

## 4. The verification scripts report success while unable to connect

This is the most consequential defect in the repository, because it is the mechanism that produced the "APPLIED to the shared Supabase project" claims.

| Command run today | Output | Exit code | Problem |
|---|---|---|---|
| `python scripts/test_connection.py` | `❌ Connection failed: … FATAL: password authentication failed for user "postgres"` | **0** | a failed DB check reports success |
| `python scripts/db/list_tables.py` | `psycopg2.OperationalError: … password authentication failed` (traceback) | **0** | traceback, still "success" |
| `python scripts/db/check_schema.py` | same traceback | **0** | same |
| `python scripts/db/verify_rls.py` | `ERROR: could not connect using DATABASE_URL: …` | **0** | prints ERROR, exits 0 |
| `python scripts/db/check_migrations.py` | `Summary: 0 gap(s) found, 1 note(s)` → **`RESULT: PASS`** | 0 | see below |
| `python scripts/check_openapi_drift.py` | `OpenAPI contract unchanged (67 paths).` | 0 | honest and useful |
| `python scripts/check_import_boundaries.py` | `import boundaries: ok` | 0 | honest and useful |
| `python scripts/check_deployment.py` | `ERROR: --base-url is required` | 0 | no deployment exists to point at |

**`check_migrations.py` never touches the database.** It parses migration SQL text with `ast` and compares it to `WORKSPACE_SCOPED_TABLES`, a hand-maintained Python list inside `verify_rls.py` ([check_migrations.py:341-394](file:///E:/EDI-Metadata_Lineage/scripts/db/check_migrations.py#L341-L394), [load_verified_tables](file:///E:/EDI-Metadata_Lineage/scripts/db/check_migrations.py#L446)). "0 gaps" means the SQL files agree with a list someone typed; it cannot detect a table that was never created, and CI runs it as a passing gate ([ci.yml:45](file:///E:/EDI-Metadata_Lineage/.github/workflows/ci.yml#L45) — labelled "static", which is honest, but the docs read the green as "applied").

Shared-DB state re-measured today: **unreachable** (`aws-0-ap-south-1.pooler.supabase.com:6543`, password auth rejected). Therefore migrations `0007`, `0008`, `0009` remain **unverified**, and every "APPLIED" header in `backend/migrations/README.md` remains an unsupported claim.

One genuinely good result: I cross-checked the column names used by [governance.py](file:///E:/EDI-Metadata_Lineage/backend/app/api/routes/governance.py) against `0009_governance.sql` — every column referenced for `freshness_sla`, `freshness_evaluation`, `incident_event` exists in the migration. So the governance slice is *schema-consistent*; it is unverified, not known-broken.

### No local substitute exists

`docker` → command not found. `psql` → not installed. No `docker-compose*`. There is **no way to stand up a Postgres on this machine**, which also means the ProvSQL ground-truth spike (M2 item 13) cannot be run here at all, and `KAIROS_LIVE_API_TESTS` cannot be satisfied locally even with correct credentials.

### 4b. Tenant isolation: the design is sound, the proof is missing

I audited every workspace-scoping mechanism by reading the DDL and the query layer, because no cross-tenant test has ever run.

| Check | Method | Result |
|---|---|---|
| Does the app connect as a privileged role? | [db.py:71-83](file:///E:/EDI-Metadata_Lineage/backend/app/db.py#L71-L83) `_apply_workspace_scope` | **No** — every transaction does `SET LOCAL ROLE kairos_app` + `set_config('kairos.workspace_id', …, true)`, and raises `RuntimeError` if the request has no workspace context |
| Is `kairos_app` safe? | [0003_personal_workspaces.sql:70-97](file:///E:/EDI-Metadata_Lineage/backend/migrations/0003_personal_workspaces.sql#L70-L97) | `NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS`, re-asserted by a guard that raises if an existing role has unsafe attributes |
| Do the core catalog tables have a workspace column + policy? | static parse of all `*.sql` | My first regex said **no** for `dataset`, `lineage_edge`, `evidence`, `raw_event`, `column_record`, `execution_run`, `audit_log` … That was **my tooling being wrong**: [0003:103-136](file:///E:/EDI-Metadata_Lineage/backend/migrations/0003_personal_workspaces.sql#L103-L136) adds `workspace_id`, `ENABLE`+`FORCE ROW LEVEL SECURITY`, and `kairos_workspace_isolation` to all 17 core tables inside a `DO $$ … EXECUTE format(…)` loop. Static text analysis cannot see DDL that is built at runtime — which is also why `check_migrations.py`'s `ast` parse (§4) can never be evidence about a database |
| Do those dynamically-scoped columns and policies exist **today**? | cannot check from this machine | **Unknown.** It depends on whether `0003` was actually applied to the shared project — precisely what §4 says nobody can verify. `verify_applied.py` must read `pg_policies` / `information_schema.columns`, not the SQL files |
| Do the 109 route SQL literals without a `workspace_id` predicate leak? | grep of every SQL literal in `backend/app` | **No, by design** — isolation is delegated to RLS plus the column default `NULLIF(current_setting('kairos.workspace_id'), '')::uuid`. Only 10 of 119 SQL literals mention workspace, and they do not need to |
| Does a missing context fail open or closed? | policy shape + [auth.py:57-68](file:///E:/EDI-Metadata_Lineage/backend/app/auth.py#L57-L68) | **Closed.** With no setting, `workspace_id = NULL` matches nothing → zero rows; `require_user` 503s before that if provisioning fails, and resets the context in a `finally` |

So the correct statement for the report and the viva is: **Kairos's isolation architecture is real and fail-closed on paper, and has never been demonstrated.** The two-workspace read/write test is in the 76 skipped tests (§1). Anyone who repeats "workspace isolation is enforced" is quoting design, not measurement — and anyone who says the core tables are unscoped is quoting a naive grep, which I ran and which was wrong.

## 5. Front end — what a user can actually do today

Ran the real dev server (`npx vite --port 5199`, backend on 8000 for the proxy) and drove it in a browser.

| Test | Result |
|---|---|
| `npx playwright test` (after `npx playwright install chromium`) | **2 passed** — but the suite asserts only that `#root` is non-empty, three containers are *attached*, `window.kairosPersonalization` exists, and no page error fired. Its own header says it deliberately avoids auth and data ([shell.smoke.spec.js:6-11](file:///E:/EDI-Metadata_Lineage/frontend/e2e/shell.smoke.spec.js#L6-L11)). CI's `shell-smoke ✅` therefore means "the HTML boots". |
| Playwright before installing browsers | **2 failed** — `chrome-headless-shell.exe` missing. The e2e gate cannot be run locally out of the box; nothing in `docs/TEAM_GUIDE.md` says to install it. |
| Landing state | Sign-in wall: `auth-stitch.html` iframe with Google/GitHub/Microsoft/Email. Below it, **"Preview dashboard with sample data"** — the only path into the product today. · [screenshot](verification-evidence/2026-11-02/01_root_login_gate.png) |
| Clicked through all 22 navigation entries in demo preview | Every view rendered. **Total API calls made by the browser: 1** (`GET /api/v1/auth/config` 200). Zero catalog, lineage, evidence, run, governance, or incident calls. |
| Mode banner | Renders **"Connected catalog mode — Views use records returned by the PostgreSQL catalog API"** in a mode that made no catalog call, immediately next to **"Demo preview · synthetic sample data — No catalog access or writes are available"**. Two contradictory statements, both visible. |
| Banner accumulation | 0 banners on entering demo → **5 after 5 further view clicks** (one appended per render, never cleared). After a normal demo run the header is a wall of ~20 duplicated banners. · [screenshot](verification-evidence/2026-11-02/02_banner_accumulation.png) |
| `/ingestion.html` (the "Import metadata" entry in the sidebar) | Returns **raw JSON to the browser**: `{"error":{"code":"UNAUTHENTICATED","message":"Sign in is required","request_id":"2741c8bc…"}}`. The route is server-gated ([main.py:151](file:///E:/EDI-Metadata_Lineage/backend/app/main.py#L151)) and proxied ([vite.config.js:46](file:///E:/EDI-Metadata_Lineage/frontend/vite.config.js#L46)); there is no HTML fallback and no redirect to sign-in. |
| React "live governance" layer | **Orphaned.** `IncidentsView.jsx` and `AssetCapabilitiesPanel.jsx` are imported by no module; `src/views/freshness.js` has no consumer at all. Only `DataModeLabel.jsx` is mounted ([main.jsx:104](file:///E:/EDI-Metadata_Lineage/frontend/src/main.jsx#L104)) — which is why the "Data provenance · DEMO FIXTURE" badge does work. Everything the user sees is legacy `app.js` rendering fixtures. |
| How the app even loads | `auth.js:6-13` injects the app scripts **after** auth succeeds, including `https://cdn.jsdelivr.net/npm/three@0.160.0` and `chart.js@4.4.4`; `auth-stitch.html:6` loads `https://cdn.tailwindcss.com` (console already warns it must not be used in production). **No internet at the demo ⇒ no styling, no charts, no 3D observatory.** |
| Console | clean apart from the Tailwind CDN warning and one 500 (my own harness error: the proxy expects the backend on port 8000). |
| Navigation vs the 14 required screens | Present: Home, Catalog (all/structure/search), Data Products, Lineage (visual/time travel/SQL/3D), Import metadata, Pipeline runs, Evidence & reasoning, Data quality, Incident console, Stewardship, Integrations & API, Preferences. **Absent from the shell entirely: Sources/connections, Freshness, Glossary, Domains, Settings (members · roles · API keys · webhooks · audit), Notifications.** |

Honesty that *does* work and should be kept: `app.js` separates `dataMode==='demo'` from `'postgresql'`, refuses to substitute samples in PostgreSQL mode ([app.js:250](file:///E:/EDI-Metadata_Lineage/frontend/app.js#L250), [app.js:252](file:///E:/EDI-Metadata_Lineage/frontend/app.js#L252)), labels the demo chart "DEMO SERIES", shows "Runtime collector NOT CONNECTED", and the SQL page states "Prototype parser, not SQLGlot" ([app.js:251](file:///E:/EDI-Metadata_Lineage/frontend/app.js#L251)). The defect is the banner and the accumulation, not the intent.

## 6. Verdict by stream

| Stream | Claimed | Measured today |
|---|---|---|
| **M1 Jatin** | auth, isolation, deployment, CI gates | Auth is fail-closed and correct. **Isolation has never been tested** (76 skipped, no token). **Deployment does not exist** (`check_deployment.py` has no base URL; `live-smoke` red 3 nights). **The verification scripts report PASS/0 while the DB is unreachable** — the green CI is partly decorative. |
| **M2 Anushka** | ingestion engine, sources, connectors | `/ingest/preview|commit` exist but the commit path (135-267) has zero coverage and hard-fails without the import-run migration, which is unapplied. **No OpenLineage receiver, no `/sources/{id}/runs`, no `/sources/health`.** Wizard endpoints exist with 31 % coverage. No scheduler. No Docker ⇒ no ground-truth spike. |
| **M3 Ashwin** | catalog, lineage, evidence, time travel | Routes exist (`/column-lineage`, `/evidence-at-time`, `/downstream-impact`) with **15-18 % coverage** and no executed request ever returned data. **No evidence explorer route, no export route, no vector search.** UI shows time-travel and evidence screens but they render fixtures because the API is never called. |
| **M4 Gauree** | governance + product shell | Governance code is schema-consistent and 28 % covered; **its UI is orphaned React that nothing mounts**, and the incident tests assert only 422s. Quality/glossary/domains/products/contracts/notifications have **no routes and no nav entries**. The shell has the banner contradiction, the accumulation bug, and CDN-only assets. |
| **M5 Pranav** | integrity + demo honesty gates | The gates exist as code (`data-mode.test.js` 10 tests, boundary checks) and pass. **None of them caught** the "Connected catalog mode" banner over fixture data, the JSON page, the orphaned views, or the false-green scripts — because they test modules, not the running product. |

## 7. What must be true before any claim in this project is repeated

1. `test_connection.py`, `list_tables.py`, `verify_rls.py`, `check_schema.py` exit **non-zero** on failure, and `check_migrations.py` prints a line that cannot be quoted as "applied".
2. A real user exists: signup → verify → sign in → `KAIROS_TEST_USER_TOKEN` set → the 76 skipped tests **run**.
3. `list_tables.py` output pasted into a PR, replacing every "APPLIED" header.
4. The browser makes at least one authenticated catalog call and the screen renders from it, with the banner matching reality.
5. `check_deployment.py --base-url <real URL>` returns 0.
6. `docs/REPRODUCIBILITY.md` §4 is deleted or rewritten against the served OpenAPI, and `python scripts/demo_m5.py` exits 0 — today the guide names 10 routes and 7 tests that do not exist, and its demo script crashes (§11).
7. `frontend/dist` is rebuilt before any deploy and `check_deployment.py` asserts the served HTML's stylesheets resolve (not that `/` returned 200) — `dist/` is gitignored, so a fresh clone has no `/` at all. The build itself is correctly styled; see §11c before believing any claim that it is not.

Until 1-5, the honest status is the one in §6: **infrastructure is real, product behaviour is unexecuted.**

## 8. Research track — executed end to end (this part genuinely works)

| Command | Result |
|---|---|
| `python research/experiments/run.py --protocol research/protocol/v1.yaml --plumbing --loss-level 0 --seed 1` | **exit 0**; warns `15 required field(s) are TBD`; writes `research/results/result_plumbing_mcar0_seed1.json` |
| Same command, twice | **byte-identical output** (sha1 `e4b7c03e…` both runs) — the pipeline is deterministic |
| Same command **without** `--plumbing` | **exit 1** with the named 15 TBD fields (`benchmark_version`, `sql_subset`, `splits.development`, `splits.validation`, `loss.replicates`, `loss.rounding_rule`, `metrics.primary`, `metrics.confidence_interval`, `aggregation`, `stopping_rule`, `exclusion_rules`, …). The integrity gate refuses a real run — exactly as documented |

**Ground truth: delegated, never computed.** [research/ground_truth/provider.py](../research/ground_truth/provider.py) defines the ABC; `ProvSQLProvider` ([provsql_provider.py](../research/ground_truth/provsql_provider.py)) and `ReferenceInterpreterProvider` ([reference_interpreter.py](../research/ground_truth/reference_interpreter.py)) both exist — **and neither is imported by any module in the repo**. The plumbing run loads truth from a checked-in fixture via `_load_ground_truth_after_prediction` ([run.py:133](../research/experiments/run.py#L133)); even the ProvSQL path only *parses a pre-exported provenance artifact* — nothing here connects to PostgreSQL or executes ProvSQL. Independence is enforced statically ([tests/test_ground_truth_independence.py](../tests/test_ground_truth_independence.py) + the import-boundary rule), which is real but is a check on imports, not on provenance.

So the honest sentence for a viva is: *"the measurement pipeline runs, is deterministic, and refuses to fake a real run; the ground-truth layer is an unclaimed stub — the 15 TBD fields and the provider wiring are the remaining research work."* That matches BENCHMARK_RESULTS.md's own disclosure.

## 9. Front end vs the real contract — both halves of the UI problem

Cross-referenced every `fetch` in the frontend against the 67-path OpenAPI contract (static map, corroborating §5's browser evidence of 1 API call in 22 clicks).

**Half 1 — screens that call endpoints that never existed (9 phantom paths):**
`/api/v1/data-products`, `/api/v1/incidents` (the real one is `/governance/incidents`), `/api/v1/proposals`, `/api/v1/proposal-decision`, `/api/v1/requests`, `/api/v1/request-submit`, `/api/v1/request-decision` (all in [app.js](../frontend/app.js)), `/api/v1/lineage/export`, `/api/v1/pii-classification` (in [pii-lineage-enhancements.js](../frontend/pii-lineage-enhancements.js)). The Data Products screen and the whole proposal/request flow can never return data even with a healthy database — the backend has no such routes.

**Half 2 — real endpoints no frontend file calls (54 of 67):** the entire `audit/*` (9), `governance/*` (9, incl. freshness, incidents, slas), `metadata/*` (5), `owner/*` (9), `rea/*` (7), `sources/*` (5 — there is no Sources screen, so §9.1's masked credentials have nowhere to render), `integrations/github/*` (5), plus `/assets/{asset_id}`, `/assets/{asset_id}/downstream-impact`, `/assets/{asset_id}/lineage`, `/lineage/{asset_id}/{direction}`, `/runs/{run_id}/dependency/{source}/{target}`, `/ingest/runs`, `/ingest/runs/{import_id}`, `/me/recently-viewed/{asset_id}`, `/metadata/bulk-update`, `/metadata/validate`, `/health`.

**Dead code shipped in the bundle:** `src/views/freshness.js`, `src/views/incidents.js`, `src/views/capabilities.js`, `src/components/IncidentsView.jsx`, `src/components/AssetCapabilitiesPanel.jsx` are imported by nothing — [main.jsx](../frontend/src/main.jsx) mounts only `DataModeLabel.jsx`. `observatory.js` and `stewardship.js` contain **zero** API references: two nav screens that fetch nothing by construction.

So the UI verdict has three tiers, not two: **missing screens** (Sources, Freshness, Glossary, Domains, Settings, Notifications — §5), **screens present but calling phantom endpoints** (Data Products, proposals/requests, PII export), and **screens present but wired to nothing** (Observatory, Stewardship, plus every backend capability with no screen at all).

## 10. Endpoint bodies executed — 60 of 72 run past auth; none verified against data

New probe ([verification-evidence/2026-11-02/probes/probe_bodies.py](verification-evidence/2026-11-02/probes/probe_bodies.py), raw output alongside): FastAPI `TestClient` with `dependency_overrides` bypassing auth, and `get_conn`/`get_db_connection` stubbed to raise a marker — **zero database contact, zero writes, zero ports**. All 72 OpenAPI operations called with minimal payloads.

| Outcome | Count | Meaning |
|---|---|---|
| Body executed past auth + validation | **60** | 44 reached the DB boundary (stub 500), 13 completed 200/400 without a DB, 3 GitHub endpoints fail-closed 503 on missing config |
| Stopped at request validation (422) | 12 | `ingest/preview|commit`, `sources` POST, audit rollback/diff, governance SLAs, metadata bulk-update/validate, owner request/search, github callback — validation layer is wired; bodies unproven with empty payloads (feed them `scripts/make_fixtures.py` output to go further) |
| Crashed on their own logic before the DB | **0** | no route 500s from Python bugs other than the stub |

Notable behaviours measured: `/lineage/{asset_id}/{direction}` returns a precise 400 for a bad direction; `/owner/assign/{asset_id}` 400s without an email; `/health` returns 200 with DB-down honesty; the `/rea/*` family returns **200 while logging `[WinError 2]` internally** — its subprocess never launches on this machine and the failure is swallowed, so whatever it renders is not from a running analysis.

**Environmental blocker found while probing:** the shared Supabase pooler is currently refusing **all** connections — `FATAL: (ECIRCUITBREAKER) too many authentication failures`, preceded by `password authentication failed for user "postgres"`. Repeated bad-credential attempts (from earlier probe sessions, possibly compounded by my own first stub-less probe attempt — stopped immediately) have tripped Supabase's circuit breaker. Until it resets, even correct credentials cannot connect, and `scripts/db/test_connection.py` will fail for reasons unrelated to its code. M1 owns both the credential question and the breaker wait; nobody should "fix" anything else against the DB until a connection succeeds once.

## 11. Documentation claims tested against the code

The docs are a second product surface: a viva examiner reads them, and a member who trusts them rebuilds the wrong thing. These are claims I checked by running or parsing, not by reading prose.

| Doc | Claim | Test I ran | Verdict |
|---|---|---|---|
| [REPRODUCIBILITY.md](REPRODUCIBILITY.md) §4 "Contract Verification Matrix" | 12 routes, each "Verified In `tests/test_api_v1.py::test_entity_endpoints`" etc. | parsed all 67 paths from `contracts/api/openapi.json`; grepped all 7 named test functions | **FALSE** — 10 of the 12 routes do not exist (`/api/v1/entities/{id}`, `/api/v1/entities/by-name`, `/lineage/{id}/graph`, `/upstream`, `/downstream`, `/evidence/{id}`, `/evidence/search`, `/evidence/entity/{id}`, `/evaluation/oracle/{run_id}`; the real surface is `/assets/…`, `/lineage/{asset_id}/{direction}`, `/evidence-at-time`), and **none** of `test_health`, `test_entity_endpoints`, `test_lineage_graph_and_truncation_headers`, `test_lineage_upstream_downstream`, `test_evidence_endpoints`, `test_m4_reasoning_and_fixed_interpretations`, `test_evaluation_oracle_isolated_mode` exists in that file. The guide describes an API generation that has been replaced |
| [REPRODUCIBILITY.md](REPRODUCIBILITY.md) §1 "Run Verification & Demo Script → `python scripts/demo_m5.py`" | the documented demo/verification entry point works | ran it | **FALSE** — prints `[1] GET /api/v1/health -> 401`, then `KeyError: 'data'` at [demo_m5.py:27](file:///E:/EDI-Metadata_Lineage/scripts/demo_m5.py#L27) because it calls the non-existent `/api/v1/entities/orders_fact` and indexes `res.json()['data']`. **Exit code 1.** So the flagship "verification demo" cannot be run in front of an examiner. (Unlike the DB probes it at least fails loudly.) |
| [REPRODUCIBILITY.md](REPRODUCIBILITY.md) §3 | `scripts/run_ui.py` "starts backend and automatically serves the compiled frontend" | read [run_ui.py](file:///E:/EDI-Metadata_Lineage/scripts/run_ui.py) (47 lines) + [main.py:159-162](file:///E:/EDI-Metadata_Lineage/backend/app/main.py#L159-L162) | **TRUE, but not by that script** — `run_ui.py` only calls `uvicorn.run("backend.app.main:app")`; the serving comes from the `StaticFiles` mount on `frontend/dist`, which is skipped when the directory is absent. `dist/` is gitignored (`.gitignore:43`), so on a fresh clone `/` 404s until you run `npm run build` (which §2 of the same guide does tell you to do) |
| v2 §5.4 connector lifecycle | the source lifecycle is a series of real stored transitions | read `0008_source_connections.sql:21-22` and every state literal in `sources.py` | **§5.4's twelve-state connector lifecycle cannot be stored.** The `CHECK` allows only `CONFIGURED / VERIFIED / ERROR / REVOKED`, and `sources.py` only ever writes `VERIFIED` / `REVOKED` / `ERROR`. `AUTHORIZED`, `DISCOVERY_*`, `NORMALIZED`, `STALE`, `SYNC_FAILED`, `CREDENTIALS_EXPIRED` would be rejected by the database (M2 A8; needs M1 migration review because 0008 is unapplied) |
| v2 §9.1 / §9.4 / §9.9 credential rules | read-only role, masked display, revoke-keeps-history | searched backend + migrations for `kairos_reader`, for a masking helper, and read `/sources/{id}/test` and `delete_source` | **§9.4 is unimplemented** — `kairos_reader` exists only in the architecture doc; `SourceCreate` accepts any user/password and nothing asserts the role is not superuser / has no write grants / lacks `SELECT ON ALL TABLES`. **§9.1 half-true** — no leak (`_load_config` decrypts server-side only, `SourceSummary` carries no credential fields) but also no masked display form anywhere in Python or JS, because there is no Sources screen. **§9.9 is satisfied** — `DELETE /sources/{id}` soft-revokes to `REVOKED` and deletes no rows, so imported evidence survives as history. `/test` also performs **discovery** and returns one state, violating the team's own "credential test ≠ discovery" rule |
| v2 §9.7 resource caps | byte/file/column/parse-time limits with diagnostics | read `main.py:31,86-92` and `ingestion/static_files/*`, plus the 413 test | **Implemented and tested** — 1 MB body cap returning `PAYLOAD_TOO_LARGE` (asserted by [test_api_v1.py:120-127](file:///E:/EDI-Metadata_Lineage/tests/test_api_v1.py#L120-L127)), `MAX_FILE_BYTES`, `MAX_COLUMNS = 1_000`, `MAX_FILES = 1_000`, each returning a named diagnostic instead of truncating. Only the **parse-time** cap is missing |
| v2 §5.5 update mechanisms | freshness updates arrive by push, scheduled pull, or Realtime invalidation | grepped for `realtime`, `channel(`, `postgres_changes`, `subscribe` across `frontend/*.js`, `frontend/src`, `backend/app`; and `APScheduler`, `cron`, `schedule`, `asyncio.create_task` across `backend/app`, `scripts`, `vercel.json` | **All three are absent.** No push receiver (§3), no scheduler (the only `schedule` hits are inside the 0 %-coverage dead modules `mock_repo.py` / `repositories/mock_repository.py`), no Realtime subscription anywhere in the product. And `0008` has no schedule or `next_sync_at` column, so two of §5.4's twelve health fields cannot be answered |
| v2 §5.6 freshness states | six states including `PAUSED` | read [freshness.py:27](file:///E:/EDI-Metadata_Lineage/backend/app/services/freshness.py#L27) vs v2 §5.6 | code has 5 states (`HEALTHY / AT_RISK / LATE / STALE / UNKNOWN`); the spec names 6 including **`PAUSED`**, which exists only in the doc. The part that *is* implemented is the honest part: no SLA or no observed activity ⇒ `UNKNOWN`, never `LATE` — the evidence-first rule is genuinely enforced |
| `backend/migrations/README.md` + headers of `0004`-`0009` | "Applied to the shared Supabase project" | §4 | **UNVERIFIABLE / probably false** — the DB rejects auth today, `check_migrations.py` never connects, and the 2026-10-30 audit measured `0005`/`0006` as absent |
| [REPRODUCIBILITY.md](REPRODUCIBILITY.md) §5 + [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md) | the 18-cell matrix is **PLUMBING ONLY**, 15 TBD fields block a real run, numbers "must not be quoted as findings" | read both docs in full; §8 has the execution result | **TRUE and honest** — this is the best-disclosed document in the repo. It self-labels, lists its own blockers, and pins `git_sha`/`mask_hash`. Any accusation of fabrication here would be wrong |
| [M5_FRONTEND_AUDIT_AND_ARCHITECTURE.md](M5_FRONTEND_AUDIT_AND_ARCHITECTURE.md), workstream docs, `TEAM_GUIDE.md`, remaining `M*_*.md` reports | per-member completion claims | delegated sweep | see §11b below |

### 11b. Remaining docs sweep — 60 claims, 8 false

Delegated sweep of `TEAM_GUIDE.md`, `docs/workstreams/*`, and every `M*_*.md` report not covered above; every claim checked by grep/ls/read against the tree at `a0621f2`. 60 claims checked: 8 **FALSE**, ~20 PARTIAL/stale, the rest TRUE or UNVERIFIABLE-without-execution.

The 8 false claims, most dangerous first:

| Claim | Where | Reality |
|---|---|---|
| "No SQLGlot import exists anywhere in the codebase" | [M4_WEEK1_CHECKPOINT.md:229](M4_WEEK1_CHECKPOINT.md) | 13 files import it, including [ingestion/sql/\_\_init\_\_.py](../ingestion/sql/__init__.py) — wrong in any era |
| "backend/migrations/ contains no migration files" | M4_WEEK1_CHECKPOINT.md:119 | `0001`–`0009` + README exist; M3's delivered work is real |
| "backend/app/temporal/ … does not exist" | M4_WEEK1_CHECKPOINT.md:136 | `reference.py` is there |
| "ingestion/sql/ directory contains only a README" | M4_WEEK1_CHECKPOINT.md:93 | `__init__.py`, `SUPPORT_MATRIX.md`, `corpus/`, `b1_adapter.py` |
| "That file [SPIKE_REPORT.md] does not exist in the repository" | M4_WEEK1_CHECKPOINT.md:76 | `research/ground_truth/SPIKE_REPORT.md` exists (truncated, but exists) |
| "dbt manifest parsing PLANNED … empty directory" | [M1_IMPLEMENTATION_AND_VIVA_GUIDE.md:46,255](M1_IMPLEMENTATION_AND_VIVA_GUIDE.md) | `ingestion/dbt/manifest.py` is implemented and dispatched by `static_files` — a teammate following the viva guide would **rebuild it** |
| Command "…tests/test_api_slice.py" | [M4_TODAY_TEST_REPORT.md:15](M4_TODAY_TEST_REPORT.md) | the file no longer exists (only a stale `.pyc`), so the cited "84/84 pass" cannot be reproduced as written |
| `M2_OPENLINEAGE_RUNTIME_ADAPTER.md` references `ingestion/openlineage/loader.py` | workstreams doc | the file does not exist (`normalizer.py`, `models.py` do) |

Systemic pattern: three point-in-time snapshots (M1 viva guide, M4_TODAY_TEST_REPORT, M4_WEEK1_CHECKPOINT) predate merges that landed M1/M2/M3 deliverables and were never re-dated. Stale-count claims (TEAM_GUIDE "34 tests / expect 31 passed", M4 per-file test counts, M3's "0001_core.sql 286 lines" — now 232) mislead anyone re-running the documented commands. Fix: date-stamp every milestone doc with its commit, and re-run the commands before quoting numbers.

### 11c. Two things I suspected and then disproved — do not turn these into tasks

Auditing by reading has a failure mode worth documenting, because both of my wrong guesses looked like severe defects and would have become someone's sprint work.

1. **"The core catalog tables have no row-level security."** A regex over every migration found `workspace_id`, `ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL SECURITY` and `CREATE POLICY` for only the newer tables, and **none** for `dataset`, `lineage_edge`, `evidence`, `raw_event`, `column_record`, `execution_run`, `audit_log`. Verdict looked like a cross-tenant leak in the product's central claim. Reality: [0003:103-136](file:///E:/EDI-Metadata_Lineage/backend/migrations/0003_personal_workspaces.sql#L103-L136) builds all of it for all 17 core tables inside a `DO $$ … EXECUTE format(…)` loop. **Static text analysis cannot see DDL constructed at runtime.**
2. **"The production build ships an unstyled UI."** `frontend/dist/index.html` contains none of the five `<link>` tags in `frontend/index.html:17-21`, and `src/main.jsx` imports only `dataMode.css` — so an authenticated user on a backend-served or Vercel deployment would see the legacy app with no styling. Verdict looked like a demo-breaking deployment bug. Reality: Vite hoists `<link href>` entries in `index.html` into the build graph, so they land in `dist/assets/index-DND5rGZc.css`. Selector overlap I measured: **224 of 228** from `styles.neo.css`, plus **61/61** `layout.css`, **25/25** `assets.css`, **3/3** `auth.css`, **11/11** `personalization.css`. The build is styled and current (`dist` was built 2026-11-01 12:16, after the newest source file).

The rule this gives the team: **a static-tool result is a hypothesis, not a measurement.** That applies double to the four `scripts/db/*` probes in §4, which are static tools reporting on a database they never contacted.

## 12. CI, delivery and deployment state

Four workflows exist; read in full, not trusted from their names.

| Workflow | What it actually asserts | Honest meaning |
|---|---|---|
| [ci.yml](../.github/workflows/ci.yml) | scoped ruff → `check_openapi_drift.py` → `check_migrations.py` (static — §4's false-green) → `npm run build` → `check_import_boundaries.py` → `pytest -q` | Real gates, but the test job runs the **offline** suite: 40 % coverage, 64/70 endpoint bodies never executed, 76 skipped live tests. `shell-smoke`-style greens here mean "code imports and offline rules hold", not "the product works". Note `from backend.api.index import app` ([ci.yml:53](../.github/workflows/ci.yml#L53)) — verified as a 4-line re-export of `backend.app.main:app`, so no Vercel/local drift. |
| [contract.yml](../.github/workflows/contract.yml) | OpenAPI drift only | Redundant with ci.yml's step; harmless. |
| [e2e.yml](../.github/workflows/e2e.yml) | 2 Playwright tests that assert the shell boots without page errors, deliberately avoiding auth and data (§5) | The `e2e ✅` badge must never be quoted as "screens work". |
| [live-smoke.yml](../.github/workflows/live-smoke.yml) | manual/nightly `check_deployment.py --base-url $KAIROS_DEPLOY_BASE_URL` — asserts `GET /health` and env-var presence | Needs a deployment to point at; per §6 there is none, so nightly runs have nothing true to assert. |

[vercel.json](../vercel.json) builds `frontend/dist` (which CI builds too — good) and rewrites `/api/*`, `/healthz`, `/ingestion.html` to `backend/api/index.py`. **No migrations step exists anywhere in the delivery path**: nothing applies `0004`–`0009` to a database at deploy time, and a Vercel function cannot run one inside a request — that is constraint D12 resurfacing. CI has no false-green guard (no step runs the `scripts/db/*` probes against a wrong password asserting non-zero — P3's recommendation), no coverage floor, and no authenticated browser test.

## 13. Who owns what — consolidated action lists

Every item below is evidenced in §1–§12 and detailed, with DoD, in the owner's handout (`docs/handouts/`).

**M1 Jatin (also: run this list — §5c of his handout is the ordered version)**
1. Fix the four `scripts/db/*` probes to exit non-zero on failure and make `check_migrations.py` unable to print "applied" without connecting (§4, P3).
2. Resolve the shared-DB credential/circuit-breaker state: one successful `test_connection.py` run, then `list_tables.py` output pasted into a PR replacing every "APPLIED" header (§10 environmental blocker, §7.3).
3. Apply migrations `0004`–`0009` (or re-plan them); review `0008`'s 4-state `CHECK` before it blocks M2 (§11 row 4).
4. Create the real test user → `KAIROS_TEST_USER_TOKEN` → run the 76 skipped tests; the two-workspace RLS test is the only proof isolation works (§4b).
5. Retire REPRODUCIBILITY §4's phantom matrix; fix or delete `scripts/demo_m5.py` (§11 rows 1–2).
6. Deliver one real deployment URL and make `check_deployment.py` assert stylesheets resolve (§7.5, §7.7).

**M2 Anushka** — A8 (widen `0008` lifecycle `CHECK` + add schedule/`next_sync_at` storage), A15 (no scheduler anywhere), A16 (all three freshness update mechanisms absent), `kairos_reader` + masked display (§11 row 5), parse-time cap (§11 row 6), wire the 12 validation-gated endpoints to `make_fixtures` payloads so preview/commit bodies get proven (§10).

**M3 Ashwin** — S-series: evidence explorer / export / vector search routes absent; `/lineage/{direction}` + `/downstream-impact` + `/assets/{id}` have coverage 15–18 % and zero executed data responses; the frontend calls **nine phantom endpoints** (§9 half 1) — decide per endpoint: build it or delete the caller.

**M4 Gauree** — K10 (`PAUSED` state + evaluation schedule storage), K11 (zero realtime wiring), mount the orphaned React governance views or delete them (§9), replace 422-only incident tests with body-level tests (§10), call `/governance/freshness|incidents|slas` from a real screen.

**M5 Pranav** — add the browser-level honesty test and claim-vs-request assertion (P1/P2), the false-green CI guard (P3), coverage-qualified report wording (P4), and re-date/verify the three stale milestone snapshots (§11b) — his own M5_FRONTEND_AUDIT doc was swept TRUE, so his bar is the one to copy.

## 14. Full sweep, same day — six parallel audits + a second browser walk

Delegated to six agents and re-walked in the live browser; raw agent verdicts are folded into the five handouts. Headline numbers:

**Frontend static inventory (~112 user-facing items):** ≈62 WORK, ≈12 BROKEN, ≈16 MISSING-BACKEND, ≈22 DECORATIVE. Worst five: `app.js:652`'s empty `save-profile` handler silently kills Preferences save; Incident console (phantom API + dead Create button); Stewardship Approve/Reject dead buttons on phantom APIs; Data Products (hidden nav + phantom API + dead Register button); "Recently viewed" permanently empty because nothing ever records a view ([personalization.js:63](../frontend/personalization.js#L63) never called). The Data-quality screen is the biggest honesty violator (4 hardcoded chart arrays + 2 invented KPIs: "Open Incidents 1", "Tier-1 Monitored 85%"). Three fully-built live views (`IncidentsView.jsx`, `views/freshness.js`, `views/capabilities.js`) are orphaned — mounting them is cheaper than fixing the app.js stubs they replace.

**Browser re-walk (16 screens, demo mode):** 13 render their own content; **Data Products and Incident console silently render the Home dashboard** (their views fall back to overview); Catalog search renders **no input field** in the document (its search form is dead on arrival in demo); banner accumulation reproduced (0 → 54 banner divs over one walk); Ctrl+K palette works (fixture results); console clean except the two known CDN warnings.

**Frontend toolchain (executed):** vitest 21/21 exit 0; `npm run build` exit 0, dist fresh; Playwright 2/2 exit 0 (shell-boot only); **no ESLint config exists at all**; `preview` script undocumented; docs claiming "11/11 tests" are stale (now 21).

**Backend routes (63 handlers classified):** 5 probe-proven wired; 14 validation-only-proven; 4 stubs; 4 broken; 36 wired-but-never-executed-with-data. New smoking guns: [dependency.py:303-315](../backend/app/api/routes/dependency.py#L303-L315) **invents a fully-covered evidence vector when the coverage JSON is absent** (absence becomes affirmation — the exact violation the architecture forbids); [audit.py:889](../backend/app/api/routes/audit.py#L889) hardcodes `unapproved_changes=0` / `access_violations=0` and an invented compliance score; [audit.py:1035](../backend/app/api/routes/audit.py#L1035) rollback **never rolls anything back** (INSERTs a PENDING row; no approve/execute path exists); [metadata.py](../backend/app/api/routes/metadata.py) bulk-update counts `pass`-no-op tag operations as successes and its bare `except Exception` turns its own 404s into 500s; `/health` returns 200 "ok" with `db="unavailable"`; `/catalog` does unbounded evidence×edge dumps.

**Test suite (executed):** 426 collected = 346 passed + 80 skipped, **41 % line coverage, 0 % of the data plane** (db.py 33 % — no SQL statement ever runs in tests; audit.py 9 %, lineage 15 %, owner 15 %, metadata 16 %, search 18 %). 12 modules at exactly 0 %. `tests/test_governance*.py` **does not exist**. `test_audit_api_live.py` (72 tests, 73 % of all skips) can pass while asserting nearly nothing (`assert status in [200,404]` + `if 200:` no-ops). `test_static_unsupported.py` skips its two flagship subjects (LEFT/RIGHT JOIN) as "unreliable in MVP-1".

**Schemas vs migrations:** no unprotected table (all 28 RLS-covered; 0003's DO-block array enumerates exactly the 17 core tables); **no CHECK-vs-code literal mismatch in code** — the only lifecycle mismatch is the v2 §5.4 twelve-state spec itself; no column-read-but-never-created. Real defects: [personalization.py](../backend/app/api/routes/personalization.py) and integrations.py **lack the `to_regclass` fail-closed guards** every other route has — with 0005/0006 unapplied they raw-500; 0007's membership tables are written and read by **nothing** (role checks unenforced anywhere); `search.py`'s `_SORTABLE` whitelist offers three sort keys the SQL never aliases (500); 0003's policy-less FORCE-RLS `kairos_workspace` breaks on any non-superuser migration owner; `REVOKE ... FROM anon, authenticated, service_role` in 0004-0009 cannot run on vanilla Postgres.

**Perplexity cross-check (121 capabilities):** 34 YES, 8 YES-PARTIAL, 41 PARTIAL, **38 NO** — of which 23 are full-scope product promises. The 15 zero-code full-scope capabilities, dependency-ordered, are the difference between "demo done" and "project 100 %": quarantine → webhook receivers → dbt run_results → query-log capture → freshness scheduler → incremental sync + connector diagnostics → quality engine → evidence strength/conflict → domains → MLflow + RAG adapters → notifications → incident routing → contracts → admin/settings → deployed URL + live-smoke. Division: M2 = 1-4, 9, 13; M4 = 5, 6, 11, 12(+RBAC); M3 = 8, 14; M2+M5 = 10, 11; M1 = 15 + RBAC + deployment gate. Each is now a numbered task with DoD in the owner's handout §6.



