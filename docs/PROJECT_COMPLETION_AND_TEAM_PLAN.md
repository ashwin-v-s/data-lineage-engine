# Kairos — Project Completion Audit & Even Five-Stream Team Plan

**Date:** 2026-10-30 · **Repo:** `github.com/ashwin-v-s/data-lineage-engine` · **Companion:** `KAIROS_ONE_PAGE_ARCHITECTURE.md`

This document does two things: (1) an honest audit of what is **done vs remaining**, measured against the code that exists today; (2) a plan that divides the remaining work into **five balanced, end-to-end workstreams (M1–M5)** so five people can work in parallel without silos or blocking each other.

---

## Part A — Verified state (measured, not aspirational)

| Check | Command | Result |
|---|---|---|
| Python test suite | `python -m pytest -q` | **261 passed, 78 skipped** (~13s) |
| Import boundaries | `scripts/check_import_boundaries.py` | ok |
| OpenAPI drift | `scripts/check_openapi_drift.py` | unchanged (51 paths) |
| DB connectivity | `scripts/test_connection.py` | PASSED — Supabase PostgreSQL 17.6 |
| Frontend build | `npm --prefix frontend run build` | success |
| Frontend unit tests | `npm --prefix frontend test` | 11/11 passed |
| Deployment smoke | `scripts/check_deployment.py` | needs a deployed base URL (none configured) |
| GitHub | 12 PRs (0 open), 59 Actions runs, `main` green | see PRs #10–#12 merged |

The 78 skips are the opt-in live-integration tests (`KAIROS_LIVE_API_TESTS=1` + secrets), not failures.

### Implemented and merged

- **FastAPI `/api/v1`** with routes: `health, search, assets, lineage, dependency, rea, audit, owner, metadata, personalization, integrations, ingest`.
- **Data layer:** migrations `0001–0006`; 17 business tables with forced workspace RLS; immutable `raw_event` trigger; `edge_temporal_version` bitemporal columns; `projection_outbox`.
- **Identity:** Supabase bearer verification; personal-workspace provisioning via SECURITY DEFINER function; `auth.py` token path.
- **Ingestion (pure):** metadata-graph, dbt manifest, file inventory, CSV-header, and SQLGlot adapters producing the shared `kairos.ingest.v1` envelope; OpenLineage normalizer.
- **GitHub connector:** AES-GCM token crypto, GitHub App service, connection store (migrations `0006`).
- **Research:** four-state engine (R1–R5), MCAR + capture manifest, protocol runner, ground-truth provider + reference interpreter, metrics, baselines, leakage guards.
- **Frontend:** Vite/React shell (`main.jsx`) + retained dashboard CSS/renderer; personalization; Playwright smoke config; Vitest suite.
- **Ops:** CI (`ci`, `contract`, `e2e`, `live-smoke`), Vercel config (`frontend/dist` + `backend/api/index.py`), OpenAPI snapshot/contract guard, RLS verifier, migration checker.

### Missing / incomplete (the real remaining work)

| # | Gap | Severity |
|---|---|---|
| G1 | **No persistent import pipeline wired to the DB** — `routes/ingest.py` exists but authenticated preview→commit→read-back is not proven end to end (migration `0004` not applied). | High |
| G2 | **No workspace membership/role model beyond owner** — no membership/invite/role tables; RBAC is workspace-only. | High |
| G3 | **Connectors are not user-driven**: no "Add source" flow, no live PostgreSQL source connector, no GitHub install/callback UI, no dbt/OpenLineage upload routes. | High |
| G4 | **No freshness, quality, or incident engine** — engine, tables, evaluator and UI absent. | High |
| G5 | **No evidence explorer / edge inspector UI**; four-state results are not surfaced on the graph. | High |
| G6 | **Search is keyword-only**; no `pgvector` semantic search, no permission-filtered retrieval. | Medium |
| G7 | **No capability registry** — UI does not gate tabs by what a resource type actually supports. | Medium |
| G8 | **Demo/fixture isolation not enforced** — no `LIVE / IMPORTED / DEMO FIXTURE` label on every view; silent fallback risk. | High |
| G9 | **No deployment** (no base URL); live-smoke has never run against a real host. | Medium |
| G10 | **Governance surfaces** (glossary, domains, data products, contracts) not built. | Medium |
| G11 | **Research results are plumbing-only**; `protocol/v1.yaml` still has ~15 TBD fields. | Medium |
| G12 | **Notifications / Realtime** not wired to the UI. | Low |

**Honest completion:** the **platform + ingestion + research plumbing** is roughly **75–80%** of a single-workspace product; the **multi-user, connector-driven, governance-complete product** the Perplexity research describes is roughly **35–40%**. The demo-critical path (G1, G3, G5, G8, G9) is what stands between today and a real signup demo.

---

## Part B — Five balanced workstreams (no silos)

Each stream is a **full vertical slice**: it owns its own migrations + API routes + UI + tests + docs. Every stream ships something a user can see. Interfaces in Part C are frozen so the five can build in parallel.

| Stream | Scope (end-to-end) | Absorbs | Load |
|---|---|---|---|
| **M1 — Identity, Workspace & Platform** | Signup/email-verify/OAuth, workspace membership + roles + invites, RLS policy tests, capability registry, deployment (Vercel+Supabase), settings/admin/audit UI, CI hardening | platform half of old M3 | ~20% |
| **M2 — Connectors & Ingestion Engine** | Ingestion orchestrator + preview/commit + idempotency + provenance; adapters (metadata graph, dbt, SQL/SQLGlot, OpenLineage, file upload, CSV); **live PostgreSQL source connector**; GitHub App install/callback; connection lifecycle + sync history | old M1 + M2 + ingestion half of old M3 | ~22% |
| **M3 — Catalog, Lineage & Evidence** | Asset catalog + detail, capability-driven tabs, 2D/3D lineage graph, column lineage, edge/evidence inspector, time travel, keyword + `pgvector` search | core of old M5 + evidence surfacing | ~20% |
| **M4 — Governance, Quality, Freshness & Incidents** | Glossary, domains, data products, contracts; freshness evaluator (SLA → HEALTHY/AT_RISK/LATE/STALE/UNKNOWN, evidence-first); quality assertions; incident lifecycle; notifications + Realtime | new product surface | ~20% |
| **M5 — Product Shell, Research & Demo Integrity** | Global shell + Home dashboard; demo-fixure isolation & `LIVE/IMPORTED/DEMO FIXTURE` labelling; research engine integrity + regression gates; E2E acceptance gates; runbook | old M4 + shell of old M5 | ~18% |

**Anti-silo rules:** every stream owns ≥1 migration, ≥1 API route, ≥1 UI screen, and its own tests. No stream is "only backend" or "only CSS". M5 owns the shared shell and the demo gate, which every other stream plugs into.

### Sprint ordering (dependency-aware)

1. **Wave 1 (unblock everyone):** M1 membership/roles + migrations `0004`; M2 ingestion commit path + envelope; M5 shell contract + label component.
2. **Wave 2 (user-visible value):** M2 Add-source + live Postgres connector; M3 catalog/detail/lineage on committed data; M4 freshness engine + incidents.
3. **Wave 3 (differentiation):** M3 evidence explorer + time travel; M4 quality + contracts; M1 `pgvector`/search + capability registry.
4. **Wave 4 (real product):** M1 deployment + live-smoke green; M5 demo gates + runbook; M4 Realtime/notifications; research protocol TBDs closed by M5.

---

## Part C — Frozen shared interfaces (so parallel work cannot collide)

Owned by M1; consumed by all. Change requires M1 review.

1. **Auth/JWT contract:** `sub`, `workspace_id`, `role`, `permissions[]`. Authorization is derived **server-side** from membership + RLS — never from client-editable claims.
2. **Ingestion envelope `kairos.ingest.v1`:** `{contract_version, source{kind,ref}, idempotency_key, assets[], relationships[], runs[], evidence[], diagnostics[], provenance{adapter,adapter_version,content_sha256}}`. `workspace_id` is server-derived.
3. **Capability response:** `{schema, preview, lineage, quality, runs, profile, usage}` each `{supported, available, reason?}` — the UI gates tabs from this, never hardcodes.
4. **Evidence record:** `{evidence_id, source_type, evidence_kind, evidence_state, subject, related_subject, observation{statement,confidence,coverage,complete_negative_evaluation}, temporal{event,valid_from/to,recorded_from/to}, provenance}`.
5. **Data-mode label:** every API response carries `source_mode ∈ {LIVE, IMPORTED, DEMO_FIXTURE}`; the shell renders it; no view may hide it.
6. **Identity/URN:** `kairos:<type>:<namespace>:<source_native_id>` + stable UUID. Display name is never identity.

---

## Part D — Acceptance gates & definition of done

- **Gate 1 (M1):** a real Supabase user signs up → verifies → signs in; unauthorized requests 401; second workspace cannot read the first.
- **Gate 2 (M2):** connect a real source → preview (no side effect) → commit once → refresh → rows read back; repeat commit is idempotent; unsupported input produces diagnostics, not empty success.
- **Gate 3 (M3):** every visible relationship shows its evidence state; a declared/parsed edge never renders as runtime-observed.
- **Gate 4 (M4):** a freshness breach creates exactly one incident and notifies the owner, with stored evidence.
- **Gate 5 (M5):** full E2E smoke passes against a deployed URL; no fixture is ever silently substituted; demo labelled.

**Definition of done:** all five gates pass on a deployed environment, `pytest` + `vitest` + Playwright smoke are green, and the OpenAPI contract snapshot is updated and committed.

---

## Part E — Open decisions blocking completion

1. Apply migration `0004` (M3 must authorize) — blocks G1.
2. GitHub auth: OAuth vs GitHub App vs fine-grained PAT (recommend App, repo-scoped read).
3. Does the first live demo require a real PostgreSQL source, or a labelled fixture?
4. dbt `manifest.json` version(s) to support; OpenLineage `kairos_` facet schema.
5. Whether table-edge bitemporal columns (`edge_temporal_version`) must be back-filled into `lineage_edge` now.
6. Rollback owner + process for schema/RLS changes on the shared Supabase project.
