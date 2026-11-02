# Kairos — Verified Project Status & M1–M5 Completion Audit

**Date:** 2026-11-02 · **Repo:** `github.com/ashwin-v-s/data-lineage-engine` · **Branch audited:** `feature/product-completion` (local)
**Method:** everything below was re-measured from this working tree today (`git fetch`, GitHub API, `pytest`, `vitest`, file reads). It supersedes the status rows in [KAIROS_HANDOFF_5_MEMBERS.md](KAIROS_HANDOFF_5_MEMBERS.md) §1 and [PROJECT_COMPLETION_AND_TEAM_PLAN.md](PROJECT_COMPLETION_AND_TEAM_PLAN.md) Part A, which were measured on 2026-10-30.

---

## 1. GitHub situation (measured today)

| Item | Value |
|---|---|
| PRs total / open | 12 / **0 open** |
| Merged | 11 (#1–#8, #10–#12) |
| Closed **unmerged** | #9 `gaureehatkar:feature/backend-ui-db-integration` — superseded by the rebase in #12 |
| Last merge to `main` | 2026-10-30 12:43Z — PR #12 (`f289897`), then PR #11 (`76eb0b0`) |
| New work on GitHub since Oct 30 | **none** |
| PR authorship | Jatin 8 · Gauree 2 · Ashwin 1 · Pranav 1 · Anushka 0 |
| Contributors (GitHub) | Jat-in32006 57 · gaureehatkar 6 · ashwin-v-s 5 · AnaaMorr 3 · pranav-samal 2 |

**CI on `main` @ `76eb0b0`:** `test` ✅ · `openapi-drift` ✅ · `shell-smoke` ✅ · `live-smoke` ❌
**Nightly `live-smoke` failures:** run #3 (2026-11-01), #2 (2026-10-31), #1 (2026-10-30) — **3 consecutive red**. Cause is not a code bug: no deployment base URL exists, so the probe has nothing to hit. `main` therefore carries a permanently failing check.

### Two things are NOT on GitHub

1. **2 unpushed commits on `feature/product-completion`** — `12488f8` "M4: research integrity gate — regression test + test report" and its merge `a0621f2`. This is Pranav's M4 gate; `origin/feature/reasoning-experiments` is the only remote branch with a commit that is not in `main`.
2. **The entire current working tree** (uncommitted): `git status` shows 14 modified + 26 untracked paths, ≈ +2,000/−800 tracked lines plus ~2,000 lines of new files. This is the bulk of the ingestion/governance/sources/capability product surface (see §3).

Nothing is stranded in the other direction: `origin/feature/m2-research-runtime-evidence`, `feature/runtime-groundtruth`, `feature/bitemporal-storage`, `feat/m5-frontend-api` are all fully contained in `main` (0 unique commits).

---

## 2. Test state today

| Suite | Result | Note |
|---|---|---|
| `python -m pytest -q` | **346 passed, 80 skipped, 0 failed** (3.7 s) | up from 261/78 on Oct 30 — the increase is all uncommitted work |
| `frontend` vitest | **21 passed** (2 files) | `data-mode.test.js` (10) is untracked, `personalization.test.js` (11) committed |
| Playwright `e2e/shell.smoke.spec.js` | not executed | exists |
| Skips, broken down | 76 opt-in live-API (`KAIROS_LIVE_API_TESTS=1`), 2 DB-gated in `test_capabilities.py`, 2 LEFT/RIGHT JOIN known-unreliable | the 76 are why "346 passed" ≠ "verified against the real database" |

### The blocker behind all "verified" claims

```
python scripts/test_connection.py
→ FATAL: password authentication failed for user "postgres"
  (aws-0-ap-south-1.pooler.supabase.com:6543)
```

The shared Supabase credentials in this machine's `.env` **do not authenticate**. Consequences:
- `scripts/db/list_tables.py`, `verify_rls.py`, `check_migrations.py` cannot run → no live table/RLS evidence.
- Migrations `0007_membership_roles.sql`, `0008_source_connections.sql`, `0009_governance.sql` each carry the header claim *"APPLIED to the shared Supabase project; the … tables exist live."* **That claim is currently unverifiable and must not be repeated in a report or demo until someone re-runs `list_tables.py` and pastes the output.** (On 2026-10-30 the same class of claim was wrong once already: `0004` said "PROPOSAL ONLY" while the table actually existed, and `0005`/`0006` were thought applied and were absent.)
- The 76 skipped live tests are exactly the tests that would prove Gate 1 (isolation) and Gate 2 (idempotent commit).
- `docs/KAIROS_FINAL_ARCHITECTURE.md` §7 "Hosted runtime" and `docs/DEPLOYMENT.md` §7 remain open.

---

## 3. What is in the uncommitted tree (the hidden ~60% of recent progress)

| New capability | Files | State |
|---|---|---|
| Persistent import: preview → commit → import-run history | [backend/app/api/routes/ingest.py](file:///E:/EDI-Metadata_Lineage/backend/app/api/routes/ingest.py) (249 + 65 lines), 4 routes `/ingest/preview`, `/commit`, `/runs`, `/runs/{id}` | staged + working-tree edits; complete-looking, offline-tested, **never run against live DB** |
| Live PostgreSQL source connector | [ingestion/postgres_source.py](file:///E:/EDI-Metadata_Lineage/ingestion/postgres_source.py) (read-only `information_schema`), [backend/app/api/routes/sources.py](file:///E:/EDI-Metadata_Lineage/backend/app/api/routes/sources.py) (448 lines, 7 routes incl. `/test`, `/preview`, `/sync`, DELETE) + encrypted credential storage | untracked; offline-passing; `sync` is manual-only |
| Governance: freshness SLA + evaluator + incident lifecycle | [backend/app/services/freshness.py](file:///E:/EDI-Metadata_Lineage/backend/app/services/freshness.py) (153 lines, pure), [backend/app/api/routes/governance.py](file:///E:/EDI-Metadata_Lineage/backend/app/api/routes/governance.py) (560 lines, 9 routes: `/slas`, `/freshness`, `/datasets/{id}/evaluate`, `/incidents` + ack/investigate/resolve) | untracked; **no scheduler — evaluation only runs when a user asks** |
| Capability registry | [backend/app/api/routes/capabilities.py](file:///E:/EDI-Metadata_Lineage/backend/app/api/routes/capabilities.py) (229 lines, `GET /assets/{id}/capabilities`) | untracked |
| Schema for the above | `0007_membership_roles.sql` (`workspace_member`, `workspace_invite`), `0008_source_connections.sql` (`source_connection`), `0009_governance.sql` (`freshness_sla`, `freshness_evaluation`, `incident`, `incident_event`) | untracked, with the unverified "APPLIED" headers above |
| Live React views | `frontend/src/api/client.js`, `src/views/{capabilities,freshness,incidents}.js`, `src/components/{DataModeLabel,AssetCapabilitiesPanel,IncidentsView}.jsx` + CSS, `src/components/dataMode.js`, wired in `src/main.jsx` | untracked |
| Contract snapshot | `contracts/api/openapi.json` +2,598 lines (all new routes) | modified, uncommitted |
| New tests | `tests/test_{capabilities,freshness,incidents,ingest_runs,pg_connector,sources_api}.py`, `frontend/__tests__/data-mode.test.js` | untracked |
| Planning docs | `docs/Perplexity/perplexity.txt`, `KAIROS_FINAL_ARCHITECTURE.md`, `KAIROS_ONE_PAGE_ARCHITECTURE.md`, `KAIROS_HANDOFF_5_MEMBERS.md`, `PROJECT_COMPLETION_AND_TEAM_PLAN.md` | untracked — **the architecture of record is not in git** |

API surface today: 16 routers, 70 route handlers (working tree) vs. 12 routers on `main`.

---

## 4. M1–M5 completion, measured against `docs/workstreams/*.md`

Weights: each milestone's own deliverable list + acceptance criteria. "Written" = code exists in this tree and has passing offline tests. "Shipped" = on `origin/main`. "Verified" = proven against the shared Supabase DB / a deployed URL.

| Milestone | Written | Shipped | Verified | Pending headline |
|---|---|---|---|---|
| **M1** static + file adapters | ~85% | ~85% | ~50% | LEFT/RIGHT-join lineage is deliberately skipped ([tests/test_static_unsupported.py:42](file:///E:/EDI-Metadata_Lineage/tests/test_static_unsupported.py#L42), 46); `dbt run_results.json` adapter **does not exist** (only `ingestion/dbt/manifest.py`); `parser_status: PARTIAL` in the M1 guide contradicts `ingestion/sql/SUPPORT_MATRIX.md` ("M1 never emits PARTIAL"); oversized/unsupported-file diagnostics not proven |
| **M2** OpenLineage runtime | ~55% | ~55% | ~20% | no persistent event path — `ingestion/openlineage/process_runtime_events.py` reads a JSONL file and **prints**; there is no `POST /ingest/openlineage`; `research/ground_truth/SPIKE_REPORT.md` is 41 lines ending mid-SQL-block (ProvSQL spike has no result); truth via `ReferenceInterpreterProvider` is human-supplied mapping = semi-automated, not machine-verified |
| **M3** ingestion API + storage | ~70% | **~30%** | **0%** | the whole import path is uncommitted; migrations 0007–0009 unverified; idempotent-commit and cross-workspace isolation are proven only by *skipped* tests; `contracts/` + `main.py` registration uncommitted |
| **M4** research integrity + evaluation | ~60% | ~40% (integrity gate unpushed) | ~40% | `research/benchmarks/` = README only → **zero real benchmark cases**; [research/experiments/run.py:329](file:///E:/EDI-Metadata_Lineage/research/experiments/run.py#L329) `run_real()` raises `NotImplementedError`; `research/protocol/v1.yaml` still has **26 TBD occurrences**; only MCAR loss exists (`missingness/mcar.py`) — operator/dataset/branch/complete-run/correlated absent; kill criteria K1–K8 unfilled; all `research/results/*.json` are `--plumbing` mock output (8 made-up units), not findings |
| **M5** frontend demo | ~55% | ~45% | ~10% | of the 7 minimum demo screens: 3 real, 4 partial/absent; no **evidence explorer**, no **edge inspector**, no **time travel**, no **quality**, no **glossary/domains/data-products** (fixture text only), no **notifications/Realtime**; PR #12 merged 3 dead `.tsx` files nothing imports |

### Against the Perplexity product spec (docs/Perplexity/perplexity.txt §17–§18)

| Screen / capability | State | Where |
|---|---|---|
| Global layout (sidebar/topbar/inspector/status) | partial | React shell + `app.js` legacy bridge |
| Home dashboard | partial | cards exist; not all metrics clickable/filtered |
| Catalog (filters, saved views, pagination) | partial | `routes/assets.py`, `search.py` keyword-only |
| Asset detail (capability-gated tabs) | partial | `capabilities.py` exists in tree; tabs not driven by it |
| Lineage graph (states, inspector, impact, time travel) | **mostly missing** | graph yes; inspector/time-travel/impact no |
| Sources (wizard, lifecycle, sync history) | built, uncommitted | `sources.py` + `views` |
| Freshness (SLA, schedule, evidence, breach→incident) | built, uncommitted, **unscheduled** | `governance.py`, `freshness.py` |
| Incidents (lifecycle, assignment, timeline) | built, uncommitted | `governance.py` |
| Quality (assertions + results) | **absent** | no table, route or UI |
| Evidence explorer | **absent** | — |
| Glossary / PII tagging | **absent** | fixtures only |
| Domains | **absent** | — |
| Data products + contracts | **absent** | fixtures only |
| Settings (members, roles, API keys, webhooks, audit) | partial | `audit.py`/`owner.py` exist; no membership/keys UI |
| Notifications + Supabase Realtime | **absent** | no code |
| Connector lifecycle states `CONFIGURED…REVOKED` | partial | `source_connection` state exists; not the full state machine |
| Hybrid search (`pgvector`) | **absent** | keyword `LIKE` only |
| Incremental sync (cursors, created/updated/unchanged counts) | **absent** | manual sync only |

### Honest composite

- Committed + green on `main` (what GitHub proves): **≈ 55%** of the product surface, **≈ 60%** of research *infrastructure*, **0%** research *findings*.
- Including the uncommitted tree: **≈ 70%** written, but **0% shipped and ≈ 0% live-verified**.
- Against the target Kairos (Perplexity spec + working multi-user demo): **≈ 40–45%**. The demo-critical path is: push the tree → restore DB access → run the live tests → schedule freshness → build the evidence explorer → deploy → green `live-smoke`.

---

## 5. Cross-cutting defects that need an owner (none are assigned today)

1. `.env` DB credentials fail → the team currently cannot verify anything against the shared project.
2. `live-smoke` red 3 nights running on `main` (no deployment; nobody owns the deploy).
3. `docs/KAIROS_FINAL_ARCHITECTURE.md`, `KAIROS_ONE_PAGE_ARCHITECTURE.md`, `KAIROS_HANDOFF_5_MEMBERS.md`, `PROJECT_COMPLETION_AND_TEAM_PLAN.md` and the Perplexity source are **untracked** — the architecture of record exists on one laptop.
4. `.github/CODEOWNERS` still lists `@M1-handle … @M5-handle` placeholders (Pack §18 was never finished) → no real review routing, which is why 4 of 5 members have ≤2 merged PRs.
5. Migration headers assert "APPLIED" without evidence (integrity risk under the team's own rule "never write 'it works' unless you ran it").
6. `docs/TEAM_GUIDE.md` and `docs/workstreams/*` still describe the pre-Perplexity scope (M1 = adapters only, M3 = single ingestion API) while `PROJECT_COMPLETION_AND_TEAM_PLAN.md` Part B already redefined the five streams — two competing definitions of M1–M5 are checked in.
7. `scripts/test_connection.py` crashes on Windows consoles (`UnicodeEncodeError` on the ❌ emoji at [scripts/test_connection.py:23](file:///E:/EDI-Metadata_Lineage/scripts/test_connection.py#L23)) — the failure is masked by a second exception.
8. `backend/app/identity/canonical_ids.py:254` is a documented `NotImplementedError` placeholder — canonical identity for at least one asset type is unfinished while §4 of the architecture calls identity LOCKED.
9. **A status claim silently flipped.** `backend/migrations/README.md` and the `0004`–`0009` headers now say **"Applied to the shared Supabase project"**, including `0005_personalization` and `0006_github_connections`, which [KAIROS_HANDOFF_5_MEMBERS.md](KAIROS_HANDOFF_5_MEMBERS.md) §1 measured as **absent** on 2026-10-30. No apply evidence was recorded, and today the credentials fail, so the claim is uncheckable. `routes/personalization.py` and `routes/integrations.py` already depend on those tables.
10. **`docs/DECISION_LOG.md` and `docs/RESEARCH_LOG.md` do not exist**, even though `TEAM_GUIDE.md` mandates them for design changes and failures. That is why the pack's D-01…D-20 decisions, the K1–K8 thresholds, and the migration-status flip above left no trace.
11. `docs/M4_TODAY_TEST_REPORT.md` reports 3 passing tests from `tests/test_api_slice.py`, a file deleted from `main` by `38d38ca` — the numbers came from the stale branch and cannot be reproduced on the merged tree.
12. **The verification scripts cannot fail.** Measured 2026-11-02: `test_connection.py`, `db/list_tables.py`, `db/check_schema.py` and `db/verify_rls.py` all report their error **and exit 0**, and `db/check_migrations.py` prints `RESULT: PASS` while never contacting the database (it compares migration text to a hand-typed list in `verify_rls.py`). CI runs it as a green gate. This is the mechanism behind defect 5 and 9 — the "Applied" claims were produced by a tool that reports success when it cannot check anything. Owner: **M1** (handout §2b J1–J4).
13. **The API layer is barely executed.** `pytest --cov` = **40 % total**, and **64 of 70 endpoint handlers have zero body lines executed** (`audit.py` 9 %, `lineage.py` 15 %, `owner.py` 15 %, `metadata.py` 16 %, `search.py` 18 %, `governance.py` 28 %, `ingest.py` 28 %, `sources.py` 31 %). `backend/app/repositories/*`, `mock_repo.py` and `schemas.py` are **0 %** — 515 statements no code imports. `tests/test_incidents.py` asserts only `422` responses; no test acknowledges or resolves an incident. "346 passed" therefore does not mean any endpoint works. Owner: **all five**, tracked in each handout §2b.
14. **The running UI is fixture-only and says otherwise.** A browser click-through of all 22 nav entries made **one** API call (`/auth/config`) while the header claimed "records returned by the PostgreSQL catalog API"; the banner also accumulates one copy per render (0 → 5 after five clicks). `IncidentsView.jsx`, `AssetCapabilitiesPanel.jsx` and `src/views/freshness.js` are imported by nothing, and six required screens (Sources, Freshness, Glossary, Domains, Settings, Notifications) have no nav entry. `/ingestion.html` shows a raw JSON 401 body to the user. Owners: **M4** (shell), **M1** (navigation auth), **M5** (the honesty gate that missed it).
15. **No test database exists anywhere.** Shared Supabase credentials fail, and this machine has no Docker and no `psql`, so there is no local substitute either. Architecture v2 §11 **D12** assigns the decision to M1 in Wave 0; until it is settled, every live-gated claim in this project is unrunnable rather than merely unverified.

---

## 6. Which document is authoritative today

The §3/§4 completion tables above were measured before the Perplexity spec was re-read line by line; the scope rows are still accurate, but the **section map they implied is not**. Read in this order:

| Doc | Role | Do not use it for |
|---|---|---|
| [KAIROS_ARCHITECTURE_V2.md](KAIROS_ARCHITECTURE_V2.md) | **architecture of record.** §4 invariants (incl. 9 no-Cartesian-OpenLineage-edges, 10 metadata ≠ data access, 11 revocation preserves history), §5 frozen contracts, **§9 Source access & credential specification**, **§10 Demo specification**, §11 open decisions D1–D10 | per-screen component inventories — those live in the checklist doc |
| [KAIROS_PRODUCT_SPEC_PERPLEXITY.md](KAIROS_PRODUCT_SPEC_PERPLEXITY.md) | the buildable inventory distilled from `docs/Perplexity/perplexity.txt` (all 2,950 lines): component counts per screen, the 7 connection-failure states, the 12 connector-diagnostics fields, freshness frequency defaults, the PII ladder, mandated vs forbidden poster wording. **§14 lists five features the spec wrongly assumes we already have.** | measured status — that is this file |
| [VERIFICATION_2026-11-02.md](VERIFICATION_2026-11-02.md) | **what was executed today, with output**: full route probe, function-level coverage, every `scripts/` check, and a browser click-through of all 22 nav entries. It is the source for the "not working" items in each handout's §2b. | claims about what works — it is the source for claims about what *does not* |
| [handouts/](handouts/README.md) | the five per-person gap lists and wave order | anything else |

Nothing in this file changes the research track: [FINAL_ARCHITECTURE_AND_RESEARCH_EXECUTION_PACK.md](FINAL_ARCHITECTURE_AND_RESEARCH_EXECUTION_PACK.md) remains binding for R1–R5, B1–B5, K1–K8 and `research/protocol/v1.yaml`.
