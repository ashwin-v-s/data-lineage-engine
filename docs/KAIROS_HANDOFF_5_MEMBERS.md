# Kairos — Five-Member Handoff: Architecture, Demo & Completion Plan

**Audience:** the five stream owners (M1–M5). **Goal:** finish the project to 100% — a real, signup-capable, multi-user demo that matches the bar set by OpenMetadata / DataHub / Atlan.
**Companions:** [KAIROS_ONE_PAGE_ARCHITECTURE.md](KAIROS_ONE_PAGE_ARCHITECTURE.md) · [PROJECT_COMPLETION_AND_TEAM_PLAN.md](PROJECT_COMPLETION_AND_TEAM_PLAN.md) · [KAIROS_FINAL_ARCHITECTURE.md](KAIROS_FINAL_ARCHITECTURE.md)

---

## 0. How to use this document

1. Read §1–§3 once (context, repo map, contracts).
2. Find your stream in §4 and work its task list top-to-bottom.
3. §5 is the wave plan — do not start a later wave's cross-cutting item until its gate is green.
4. §6 is the demo you are all building toward; §7 is the definition of done.
5. §8 lists the decisions that need a human answer before the related task can finish.

---

## 1. Verified starting point (2026-10-30)

| Signal | Result |
|---|---|
| `pytest -q` | 261 passed, 78 skipped (live tests are opt-in) |
| `check_import_boundaries.py` | ok |
| `check_openapi_drift.py` | unchanged (51 paths) |
| `npm --prefix frontend run build` | success |
| `npm --prefix frontend test` | 11/11 |
| `scripts/test_connection.py` | PASSED — Supabase PostgreSQL 17.6 |
| Deployment | none (no base URL); `live-smoke` never run against a host |

**Live DB tables (queried, not inferred):** `dataset, column_record, job, execution_run, raw_event, evidence, lineage_edge, edge_temporal_version, execution_state, projection_outbox, team_member, owner_assignment, owner_request, audit_log, asset_version, audit_event, rollback_record, kairos_workspace, import_run` (19).

**Migration truth vs. the file headers:**

| Migration | File says | Live DB | Action |
|---|---|---|---|
| 0001–0003 core / audit / workspaces | applied | present | ✅ |
| 0004 import_run | "PROPOSAL ONLY" | **table exists** | ✅ present; fix the stale header (M1) |
| 0005 personalization (`asset_view`, `asset_star`) | applied | **absent** | ⚠️ must be applied (M4) |
| 0006 github_connection | not applied | **absent** | ⚠️ apply before enabling GitHub (M2) |

`verify_rls.py` reports 17/20 because 0005/0006 tables are missing and because the *verifying* role (`postgres`) bypasses RLS — the app runs as `kairos_app`, so that is a harness note, not app breakage.

---

## 2. Architecture (what we are building)

Kairos = **evidence-first data intelligence**. Four layers, one authoritative store.

```
Layer D  Product dashboard      Catalog · Asset Detail · Lineage · Sources · Quality · Incidents · Freshness · Evidence · Glossary · Domains · Data Products · Settings
Layer C  Product backend        FastAPI /api/v1 · capability registry · bearer auth · ingestion orchestrator
Layer A  Research core          SQLGlot · dbt · OpenLineage → evidence → four-state reasoning → ground-truth eval (ISOLATED)
Layer B  Connectors             one contract, many adapters: postgres · github · dbt · openlineage · sql · upload · mlflow
────────────────────────────────────────────────────────────────────────────────
Store:   PostgreSQL on Supabase (authoritative). pgvector for search. Neo4j = optional rebuildable projection (deferred).
Identity: Supabase Auth → JWT → server-side workspace membership + role → RLS.
```

**Hard invariants (do not violate):**
1. PostgreSQL is the single source of truth. Nothing else stores authoritative state.
2. Missing evidence → `UNKNOWN`/`POSSIBLE`. It is **never** rendered as a negative edge.
3. Ground truth (`PROPAGATED`/`NOT_PROPAGATED`) never enters predictors, reasoning, or user-facing conclusions.
4. A source credential authorizes *Kairos' backend* to read a source; Kairos RLS/RBAC authorizes *a user* to see imported metadata. These are separate.
5. No fixture is ever silently substituted for a failed live call. Every record carries `source_mode ∈ {LIVE, IMPORTED, DEMO_FIXTURE}`.
6. Authorization is enforced server-side (API + RLS), never by hiding UI.

---

## 3. Repository map

| Area | Path | Owner |
|---|---|---|
| API routes | `backend/app/api/routes/*.py` (`health, search, assets, lineage, dependency, rea, audit, owner, metadata, personalization, integrations, ingest`) | per-stream |
| App/shared | `backend/app/main.py`, `auth.py`, `db.py`, `api/errors.py` | M1 |
| Schemas | `backend/app/schemas/*.py` | per-stream |
| Migrations | `backend/migrations/0001..0006*.sql` | M1 (owner), authors per stream |
| Ingestion adapters | `ingestion/{static_files,dbt,openlineage,sql,metadata_graph}/` | M2 |
| Research core | `research/{reasoning,missingness,metrics,baselines,ground_truth,protocol,experiments}/` | M5 |
| Frontend | `frontend/src/main.jsx` (React shell), `frontend/{app.js,ingestion.js,...}` (legacy bridge), `frontend/*.css` | M3/M5 |
| Contract | `contracts/api/openapi.json`, `scripts/check_openapi_drift.py` | M1 |
| Tests | `tests/*`, `frontend/__tests__/*`, `frontend/e2e/*` | per-stream |
| Ops | `vercel.json`, `.github/workflows/{ci,contract,e2e,live-smoke}.yml`, `scripts/*` | M1/M5 |

---

## 4. The five streams — detailed handoff

Each stream owns migrations + routes + schemas + UI + tests for its slice, and one shared interface. **No stream is backend-only or CSS-only.**

### M1 — Identity, Workspace & Platform (owner of the contract)
**Mission:** make "a real user can sign up and safely use the product" true and enforceable.
Tasks:
1. `0007_membership_roles.sql`: `workspace_member(workspace_id, user_id, role, status, invited_by, created_at)`, `workspace_invite`; RLS on both; grant to `kairos_app`; backfill the personal workspace owner as `admin`.
2. `GET /api/v1/workspaces/me`, `GET/POST /api/v1/workspaces/{id}/members`; role checks server-side; permissions derived from membership, **never** from JWT `user_metadata`.
3. **Capability registry** (`GET /api/v1/assets/{id}/capabilities`) returning `{schema,preview,lineage,quality,runs,profile,usage}` each `{supported, available, reason?}` — the frozen interface M3 renders.
4. Deployment: Vercel project + env (`DATABASE_URL, SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, FRONTEND_ORIGIN`), run `scripts/check_deployment.py --base-url`, get `live-smoke` green.
5. Housekeeping: fix the stale "PROPOSAL ONLY" header on `0004` and the `migrations/README.md` state; update `contracts/api/openapi.json`.
Acceptance: a real signup→verify→sign in; unauthorized → 401; workspace B cannot read workspace A. Tests: `tests/test_auth_workspace.py` (new), RLS cross-tenant test.

### M2 — Connectors & Ingestion Engine (owner of `kairos.ingest.v1`)
**Mission:** every source a user authorizes materializes through one honest, idempotent pipeline.
Tasks:
1. Verify end-to-end: `POST /api/v1/ingest/preview` (no writes) → `POST /api/v1/ingest/commit` (writes once) → read back via catalog; repeat commit with same `idempotency_key` returns `replayed:true`.
2. Add `GET /api/v1/ingest/runs` (from `import_run`) + `GET /api/v1/ingest/runs/{id}`.
3. Add OpenLineage + SQL routes into the same envelope (`kind: "openlineage"`, `kind: "sql"`); connector lifecycle states `CONFIGURED…REVOKED`.
4. **Live PostgreSQL source connector** (read-only role, `information_schema`/`pg_catalog`) → assets only, `POSSIBLE` lineage.
5. GitHub: apply `0006`, wire install/callback, repo-scoped read.
6. Connection health + sync history endpoints.
Acceptance: connect → preview → commit once → refresh → rows persist; duplicate commit is idempotent; unsupported input → diagnostics, not empty success. Tests: `tests/test_ingest_pipeline.py`, `tests/test_pg_connector.py`.

### M3 — Catalog, Lineage & Evidence (owner of the evidence contract)
**Mission:** the differentiator — every conclusion shows *why*.
Tasks:
1. Catalog list/detail + capability-driven tabs (render from M1's registry; never hardcode).
2. Lineage graph (2D/3D) with direction/depth/column toggle; **edge inspector** showing `relationship_type, state, evidence source, evidence_id, confidence, coverage, valid_time, recorded_time, explanation`.
3. **Evidence explorer**: raw + normalized view, provenance chain, conflict view, temporal view.
4. Time travel: query `edge_temporal_version` (table-edge bitemporal columns) — disclose undated rows rather than implying complete history.
5. Search: keyword + `pgvector` hybrid, permission-filtered.
Acceptance: a declared/parsed edge never renders as runtime-observed; every edge click shows real evidence rows. Tests: `tests/test_lineage_evidence.py`, `frontend/__tests__/edge-inspector.test.js`.

### M4 — Governance, Quality, Freshness & Incidents
**Mission:** real monitoring, traceable to stored rows.
Tasks:
1. Apply `0005`; add `freshness_*`, `quality_assertion`, `quality_result`, `incident` tables (`0008_governance.sql`).
2. Freshness evaluator: SLA → `HEALTHY/AT_RISK(>80%)/LATE/STALE/UNKNOWN`; evidence-first (never LATE without evidence); scheduled every 15 min/hourly; source-specific signal (OpenLineage run, dbt `run_results`, `updated_at`, manual).
3. Quality assertions (freshness/completeness/uniqueness/validity/schema/custom SQL) + results.
4. Incidents: create on LATE/failed test, owner assignment, timeline (detected→ack→investigating→resolved), notifications.
5. Glossary, domains, data products, contracts (ODCS-shaped).
Acceptance: a freshness breach creates exactly one incident, notifies the owner, and stores evidence. Tests: `tests/test_freshness.py`, `tests/test_incidents.py`.

### M5 — Product Shell, Research & Demo Integrity
**Mission:** the shell, the honesty layer, and the research gates.
Tasks:
1. Global shell (sidebar/topbar/inspector/status bar) + Home dashboard (health, incidents, source health, freshness, lineage, activity, runs, my-ownership) — every metric clickable.
2. **Data-mode label component** + eliminate silent fixture fallback: every view shows `LIVE | IMPORTED | DEMO FIXTURE`; a failed live call shows an explicit error, never a fixture.
3. Research integrity: close the ~15 TBD fields in `research/protocol/v1.yaml`; keep truth-separation tests green (`test_ground_truth_independence.py`).
4. E2E acceptance gates + `docs/DEMO_SCRIPT.md` + runbook.
Acceptance: forcing an API failure renders no fixture; demo is labelled; Playwright smoke green on the deployed URL. Tests: `frontend/e2e/*`, `tests/test_ground_truth_independence.py`.

---

## 5. Wave plan (dependency-aware)

| Wave | Goal | Streams | Gate |
|---|---|---|---|
| **1 — Unblock** | membership + roles migration; confirm ingest commit path; shell contract + data-mode label component; apply 0005/0006 | M1, M2, M5 | signup works; commit path verified; label component exists |
| **2 — User value** | Add-source + live PostgreSQL connector; catalog/detail/lineage on committed data; freshness engine + incidents | M2, M3, M4 | connect→commit→read back; graph shows evidence states; breach→incident |
| **3 — Differentiation** | evidence explorer + time travel; quality + contracts; hybrid search + capability registry in UI | M3, M4, M1 | edge inspector + evidence explorer real; search permission-filtered |
| **4 — Real product** | deploy + live-smoke; demo gates + runbook; Realtime/notifications; research TBDs closed | M1, M5, M4 | all §7 gates pass on a deployed URL |

---

## 6. The demo (what a user does)

**"Sign up, connect a source, see evidence-based lineage."**

1. **Sign up** at the deployed URL → Supabase email verification → sign in. *(Identity ≠ source access.)*
2. **Home** → "What needs my attention?" cards; every number is clickable and filtered.
3. **Sources → Add source** → choose PostgreSQL (read-only creds) or GitHub (repo-scoped) or upload a `kairos.ingest.v1` JSON / dbt manifest / OpenLineage event.
4. **Preview** → counts, warnings, unsupported content, provenance. No side effects.
5. **Commit** → one transaction, idempotent; import-run + audit recorded.
6. **Catalog → Asset Detail** → schema, owners, freshness, quality — tabs gated by the capability registry.
7. **Lineage** → click any edge → *why this edge exists*: state, evidence source/ID, confidence, coverage, valid vs recorded time.
8. **Evidence explorer** → raw → normalized → canonical asset provenance chain.
9. **Freshness / Incidents** → a breach exists because stored evidence says so.
10. **Honesty moment** → point at the `LIVE / IMPORTED / DEMO FIXTURE` label and state the limits: keyword vs semantic search, sample vs connected catalog.

**Say out loud:** what Kairos proves and, equally, **what it does not** (SQL parse ≠ execution; dbt declaration ≠ run; absent OpenLineage ≠ non-propagation).

---

## 7. Definition of done

- **Gate 1 (M1):** real signup→verify→sign in; unauthorized requests 401; workspace isolation proven by a two-workspace test.
- **Gate 2 (M2):** connect→preview→commit once→refresh→read back; repeat commit idempotent; unsupported input → diagnostics.
- **Gate 3 (M3):** every edge shows a real evidence state; no fixture edge masquerades as runtime-observed.
- **Gate 4 (M4):** a freshness breach creates one incident + owner notification, with stored evidence.
- **Gate 5 (M5):** E2E smoke green on the deployed URL; a forced API failure shows an error, not a fixture; demo labelled.
- **All:** `pytest` + `vitest` + Playwright green; OpenAPI snapshot updated; `live-smoke` green; no stream's tests depend on another stream's unmerged code (frozen interfaces only).

---

## 8. Decisions that need a human answer

1. Apply `0005` and `0006` to the shared Supabase project? (0005 is required for the personalization feature that already has code.)
2. GitHub auth: GitHub App (recommended, repo-scoped read) vs OAuth vs fine-grained PAT.
3. First live demo source: real PostgreSQL, or a labelled fixture?
4. dbt `manifest.json` supported version(s); the `kairos_` OpenLineage facet schema.
5. Back-fill bitemporal columns from `edge_temporal_version` into `lineage_edge`, or keep table-edge time travel explicitly limited?
6. Rollback owner + approval process for schema/RLS changes on the shared project.

---

## 9. Onboarding commands

```powershell
pip install -e ".[dev]"                      # backend + tests
python -m pytest -q                          # 261 pass / 78 skip baseline
python scripts/db/check_migrations.py        # static migration view
python scripts/db/list_tables.py             # live table check
python scripts/test_connection.py            # DB connectivity
npm --prefix frontend ci; npm --prefix frontend run build; npm --prefix frontend test
# live integration (opt-in):
$env:KAIROS_LIVE_API_TESTS=1; python -m pytest -q tests/test_live_api.py
# deployment smoke (needs a deployed URL):
python scripts/check_deployment.py --base-url https://<your-deployment>
```
