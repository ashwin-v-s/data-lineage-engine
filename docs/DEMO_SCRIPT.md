# Kairos — Demo Script and Viva Runbook

**Based on:** Architecture v2 §10 · `PROJECT_STATUS_2026-11-02.md`
**Owner:** M5 (Pranav `pranav-samal`) — Research Integrity & Demo Honesty
**Status:** Local prototype demo (no deployed URL yet — live-smoke pending M1/Ashwin)

---

## Pre-conditions checklist (verify before any demo)

Run these in order. Do not proceed to the demo if any step fails.

```powershell
# 1. DB connection
python scripts/test_connection.py
# Expected: "Connection test PASSED"

# 2. Migrations applied
python scripts/db/check_migrations.py
# Expected: "RESULT: PASS", 9 migrations, 0 gaps

# 3. Server starts
python -m uvicorn backend.app.main:app --port 8000 &
# Expected: "Application startup complete"

# 4. Public liveness probe
curl http://localhost:8000/healthz
# Expected: {"status": "ok"} or similar, 200

# 5. Offline verification script
python scripts/demo_m5.py
# Expected: "RESULT: ALL CHECKS PASSED", exit 0

# 6. Live tests (if token available)
# KAIROS_LIVE_API_TESTS=1 KAIROS_TEST_USER_TOKEN=<token>
# pytest tests/test_live_api.py tests/test_ingest_runs.py tests/test_workspace_scope.py -v
# Expected: 13+ passed
```

---

## Demo flow — 12 steps

### Step 1 — Sign in
**What happens:** Navigate to the app URL. Enter email and password registered
on the shared Supabase project. Click Sign In.

**What is demonstrably real:** Supabase Auth validates credentials. The API
provisions a personal workspace server-side if none exists. All subsequent
requests carry a bearer token.

**Fails if:** Email not confirmed, Supabase project unreachable, or
`KAIROS_AUTH_DISABLED` is false and no valid token is returned.

**Presenter says:** *"Sign-in is handled by Supabase Auth. The API validates
the token and isolates all data to this workspace."*

---

### Step 2 — Dashboard / Home
**What happens:** The home screen loads. Cards show workspace summary.

**What is demonstrably real:** The shell renders and the auth token is accepted.

**Honest limit:** Some dashboard cards may show placeholder counts until
catalog data is imported.

**Presenter says:** *"This is a personal workspace. No data from other
workspaces is visible here — that is enforced by PostgreSQL Row Level Security."*

---

### Step 3 — Navigate to Import Metadata
**What happens:** Click Import or Sources in the sidebar.

**What is demonstrably real:** The ingest preview endpoint exists and is
auth-gated (`/api/v1/ingest/preview`).

**Fails if:** The route returns 404 (means the ingest router is not registered).

---

### Step 4 — Upload a metadata graph JSON fixture
**What happens:** Upload `frontend/sample_metadata_graph.json` (the documented
sample fixture).

**What is demonstrably real:** The preview endpoint validates and returns
counts, provenance, warnings, and unsupported content.

**Honest limit:** The preview has no database side effect. Nothing is persisted
until Step 6.

**Presenter says:** *"This is a preview — no data has been written yet. You can
see what would be imported, including any warnings or unsupported constructs."*

---

### Step 5 — Inspect preview results
**What happens:** The UI shows asset counts, relationship candidates, evidence
classifications, and any diagnostics.

**What is demonstrably real:** Static declarations are labelled
"Declared dependency (static analysis)" — never "Observed". Any unsupported
construct shows a diagnostic, not a silent empty success.

**Fails if:** A static edge shows "Observed" or a parse error is silently ignored.

**Presenter says:** *"Every edge shows its source: static analysis or runtime
observation. A parsed SQL dependency is declared — it does not mean the query ran."*

---

### Step 6 — Confirm Import
**What happens:** Click Confirm. The API calls `/api/v1/ingest/commit`.

**What is demonstrably real:** One transaction writes assets, relationships,
evidence, and an import-run record. The same idempotency key does not
create duplicate records on retry.

**Fails if:** The commit endpoint returns non-200, or a second identical
request creates duplicate rows (idempotency failure).

**Presenter says:** *"Import is explicit and idempotent. Submitting the same
file twice does not create duplicate records."*

---

### Step 7 — Refresh and read back from Catalog
**What happens:** Navigate to Catalog. The imported assets appear.

**What is demonstrably real:** Assets are read from the Supabase database via
`/api/v1/catalog`, filtered to this workspace by RLS.

**Fails if:** The catalog is empty after a successful import (persistence failure
or RLS misconfiguration).

**Presenter says:** *"These assets are read back from the database — they
survived a page refresh. This is connected catalog data, not a fixture."*

---

### Step 8 — Open an asset — Lineage view
**What happens:** Click an asset. Navigate to the Lineage tab.

**What is demonstrably real:** The lineage graph shows nodes and edges with
evidence labels. Each edge shows its source system and evidence classification.

**Fails if:** An edge shows "Observed" for a static-only import (no runtime
evidence was provided in Step 4).

**Presenter says:** *"This edge is labelled 'Declared dependency' because it
came from static SQL analysis. It does not say 'Observed' — that would require
a runtime OpenLineage event confirming the query executed."*

---

### Step 9 — Show workspace isolation
**What explains it:** The database uses PostgreSQL RLS. Every query runs as the
`kairos_app` role with workspace context set. A second user sees only their own
workspace data.

**What is demonstrably real:** `tests/test_workspace_scope.py` (3 tests, all
passing live) verifies the RLS enforcement at the connection level.

**Honest limit:** A live two-user demo requires two registered accounts and
two browser sessions. With one account, cite the passing test as evidence.

**Presenter says:** *"Workspace isolation is enforced at the database level by
PostgreSQL Row Level Security. The test suite verifies this — it is not just
application logic."*

---

### Step 10 — Governance: Freshness SLA (if configured)
**What happens:** Navigate to Freshness or Governance.

**What is demonstrably real:** The SLA and evaluate endpoints exist and are
auth-gated. Evaluation is on-demand (no scheduler running yet).

**Honest limit:** No automatic scheduler is running. Evaluation only runs when
triggered via the API. State this clearly.

**Presenter says:** *"Freshness evaluation is available on-demand. Automatic
scheduling is not yet wired — that requires a Supabase Edge Function or GitHub
Actions cron, which is a Wave 4 item."*

---

### Step 11 — Research integrity gate
**What happens:** Run the offline test suite.

```powershell
python -m pytest tests/test_engine_rules.py tests/test_leakage.py
  tests/test_ground_truth_independence.py tests/test_baselines.py
  tests/test_metrics.py tests/test_mcar.py tests/test_protocol_runner.py
  -q -p no:langsmith_plugin
```

**What is demonstrably real:** 81 research tests pass. Four-state engine
rules R1–R5 are tested including adversarial mutation. Ground-truth isolation
is tested at three layers (module boundary, AST check, runtime scan).

**Presenter says:** *"81 offline research tests pass. The engine returns POSSIBLE
when evidence is missing — it never treats an absent event as proof of no
lineage. That is enforced by the test suite."*

---

### Step 12 — Honest limits closing
**Presenter says out loud:**

> "What you have seen is a local prototype. Three things are not yet complete:
> first, there is no deployed URL — Vercel deployment is pending infrastructure
> setup. Second, the research experiment has benchmark cases but `run_real()`
> is not yet wired to the ground-truth provider. Third, automatic freshness
> scheduling requires a scheduler that is not yet running.
>
> Everything shown — sign-in, import, catalog readback, lineage labels, and
> workspace isolation — is real and backed by a passing test or a database query.
> We are not claiming more than that."

---

## Viva Q&A evidence table

| Claim | Evidence |
|---|---|
| Auth is fail-closed | 66/68 routes return 401 without token (VERIFICATION_2026-11-02.md §2) |
| Missing events never imply refutation | `test_missing_runtime_evidence_never_refutes` in `test_engine_rules.py` |
| Ground-truth isolation holds | `test_ground_truth_independence.py` (2 tests) + `test_leakage.py` (4 tests) |
| Workspace RLS is enforced | `tests/test_workspace_scope.py` (3 tests, live-passing) |
| Import is idempotent | `tests/test_live_ingestion_storage.py::test_commit_is_idempotent_*` (live) |
| 9 migrations applied | `python scripts/db/check_migrations.py` → RESULT: PASS |
| Static ≠ Observed | All static edges labelled "Declared dependency" (Section 5, M4_TODAY_TEST_REPORT.md) |
| Four-state rules R1–R5 correct | Adversarial mutation test in `M4_DAY1_REVIEW.md` §5 caught by 7 tests |
| Protocol is reproducible | `run_plumbing()` is deterministic (same seed = same hash, 3 tests) |

---

## Claim vocabulary (mandatory phrasings — do not deviate)

| Use this | Never say |
|---|---|
| "Declared dependency (static analysis)" | "Observed" for a static edge |
| "Observed in run [run_id]" | "Live lineage" without a runtime event |
| "No runtime evidence captured" | "No lineage" for a missing event |
| "Complete evaluation: no propagation for this run" | "This dependency does not exist" |
| "Supabase-hosted PostgreSQL is our single authoritative store" | "Supabase automatically shares data" |
| "Scheduled freshness monitoring — on-demand only, no scheduler yet" | "Real-time monitoring" |
| "81 offline tests pass; 0 endpoint bodies verified against a DB in isolation" | "All tests pass" (unqualified) |

---

## What is NOT in the demo (be explicit if asked)

| Feature | Status |
|---|---|
| Deployed public URL | Pending Vercel infrastructure (M1 Jatin / Ashwin) |
| `run_real()` experiment | Protocol filled; benchmark cases written; runner not yet wired |
| Automatic freshness scheduler | Not running — on-demand only |
| ProvSQL ground truth | Downgraded to ReferenceInterpreterProvider (RESEARCH_LOG.md R-01) |
| Playwright E2E against deployed URL | Pending deployed URL |
| Quality assertions, glossary, domains, notifications | Not implemented |
