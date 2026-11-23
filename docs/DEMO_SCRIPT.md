# Kairos — Ten-demo runbook

**For:** the 2026-11-08 presentation

**Scope:** run the real local application against the shared Supabase project. This runbook distinguishes verified behavior from steps requiring external credentials.

## Before presenting

1. Start the backend and React frontend using the repository setup instructions. Confirm `/healthz` returns HTTP 200 and open the frontend through its configured dev server (not by opening an HTML file directly).
2. Sign in with a confirmed Supabase account. Check that API calls carry that user's access token. Never present the auth screen as proof of authentication by itself.
3. Import small, prepared files into a disposable workspace and confirm they appear in catalog/API readback. Do not populate the shared workspace with fabricated customer data.
4. Keep the readiness report open. If a required external integration is not configured, present its implementation and clearly label the step as awaiting credentials rather than pretending it ran live.

## Ten demo flows

| # | Demo | Presentation flow | Verified limit / prerequisite |
|---|---|---|---|
| 1 | Sign-in and workspace isolation | Sign in, show the welcome email in the account inbox, switch workspaces, and show workspace-scoped catalog/member access. | Welcome delivery requires SMTP and a public app URL in backend environment. Live database migrations and `kairos_app` RLS isolation are verified. Still run the separate two-real-user Supabase token check before claiming end-to-end auth isolation. |
| 2 | PostgreSQL source | Add one of the five disposable read-only PostgreSQL databases listed in `.demo-sources/README.md`, test it, scan/sync, and show discovered assets. | Five logical databases with synthetic tables and a read-only connector role are provisioned in the existing Supabase PostgreSQL cluster. The adapter scan and write denial are verified. Restart the backend to load the local token-encryption key, then complete test → preview → sync → catalog readback with a confirmed Kairos user. They are not five separate Supabase projects. |
| 3 | Local folder | Choose `docs/demo-fixtures/` explicitly in the browser, inspect the inventory, preview `metadata_graph.json`, validate, commit, then show catalog readback. | Directory access is limited to the user-selected folder; inventory alone does not ingest file contents. The sample files contain synthetic metadata only. |
| 4 | Private GitHub | Connect the installed Kairos GitHub App, select an authorized repository/branch, browse and preview a file. | Requires GitHub App ID/private key/client credentials, encryption key, callback URL, installation, and test repo. Preview is not catalog ingestion. |
| 5 | SQL parsing | Preview `docs/demo-fixtures/demo_revenue.sql`; inspect the declared target and source candidates, validate, commit, then read the catalog/evidence. | Parser output is static evidence, not proof that the query executed. Unsupported/plain SELECT does not imply a target or lineage edge. |
| 6 | dbt manifest | Preview `docs/demo-fixtures/manifest.json`, inspect the model and two sources, commit, and read back assets/lineage. | The included manifest is synthetic and intentionally small; it demonstrates declared dependencies, not a dbt run or test execution. |
| 7 | OpenLineage | Send a runtime event with the configured bearer secret; show run/evidence/lineage readback. | Requires `KAIROS_OPENLINEAGE_WEBHOOK_SECRET` and `KAIROS_OPENLINEAGE_WORKSPACE_ID` on the backend and matching producer configuration. Binding is single-workspace. |
| 8 | Coverage-aware lineage | Open lineage for an imported asset, inspect upstream/downstream edges and evidence. | Do not claim full column coverage or time-travel semantics unless demonstrated by an acceptance case; graph visibility alone is not coverage proof. |
| 9 | Freshness, quality, incidents | Open freshness and quality views, create/inspect an assertion or incident, demonstrate assignment and resolution. | Requires live workspace data and write/readback validation. Scheduled evaluation and notification delivery are not verified; scheduler ownership remains a team decision. |
| 10 | Governance | Create a term/domain/product/classification/contract using real selected assets, then reopen it from the API-backed view. In Workspace administration, invite an email, confirm delivery, accept the seven-day link while signed in with the same email, then switch to the invited workspace. | Invitation/welcome email requires SMTP and a public app URL. Migration and reads are verified. Validate mutation and readback in the presentation workspace before calling the full flow live. |

## Evidence commands

Run from the repository root in PowerShell:

```powershell
python scripts/test_connection.py
python scripts/db/check_migrations.py
python scripts/db/verify_applied.py
python scripts/db/verify_rls.py
python scripts/db/verify_workspace_isolation.py
python -m pytest -q
npm --prefix frontend test -- --reporter=dot
npm --prefix frontend run build
```

These commands verify repository and database state. They do not substitute for the external integration prerequisites in the table. Do not print or commit `.env`, tokens, OAuth secrets, or private keys.

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

## Demo 7 — OpenLineage event → persisted runtime evidence

**Goal:** a job and dataset pair that does not exist yet in the demo workspace
becomes raw event → execution run → evidence → asset match → lineage edge →
provenance, with no manual SQL.

**Pre-condition:** signed in. The endpoint writes into workspace-scoped tables,
so it requires the same bearer token a signed-in user carries; it will not guess
a workspace. Set `TOKEN` from the browser session before running these.

**1. Preview (writes nothing — safe to run twice on stage):**

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/ingest/openlineage/preview \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "eventType": "COMPLETE",
    "eventTime": "2026-11-15T10:15:00Z",
    "producer": "https://github.com/OpenLineage/OpenLineage/tree/1.9.0/integration/spark",
    "job": {"namespace": "kairos.demo", "name": "new_revenue_job"},
    "run": {"runId": "run_999"},
    "inputs":  [{"namespace": "postgres://analytics", "name": "analytics.public.orders"}],
    "outputs": [{"namespace": "postgres://analytics", "name": "analytics.public.revenue_daily"}]
  }'
```

Expected: `count: 1`, `valid_count: 1`, and a normalized summary naming
`new_revenue_job`, `run_999`, the input and the output.

**2. Commit the same body to `/api/v1/ingest/openlineage`.**
Expected counters: `accepted: 1`, `runs_written: 1`, `evidence_created: 1`,
`edges_created: 1`.

**3. Replay the identical body.** Expected: `duplicate: 1` and every other
counter `0` — the raw event is stored once and no second edge is created.

**4. Read it back from the product, not from SQL:** reload the catalog and show
three things on the same screen — the evidence row with `state: "OBSERVED"`, the
new edge, and the run for `run_999` with status `SUCCESS` on the Runs page.

**5. Lineage view.** The new edge is drawn solid (Observed), not dashed
(Possible), and clicking it opens the aggregate: state, coverage, basis and the
evidence sources behind it.

**Presenter says:** *"This relationship is Observed in run_999. The event named
exactly one output, so one dataset edge was created — a multi-output event
records evidence only, never a cartesian product of edges."*

**Never say:** *"Live lineage."* One event is a snapshot, not a stream.

---

## Demo 8 — Coverage-aware lineage and impact analysis

**What is on screen:** every dependency carries one of four states —
`OBSERVED` (a runtime event proves it for a run), `POSSIBLE` (declared or static
only), `REFUTED_FOR_RUN` (a complete negative evaluation for one run, never a
universal refutation) or `UNKNOWN` (nothing stored). Coverage is `COMPLETE`,
`PARTIAL` or `NONE`, computed by `kairos.coverage.v1`.

**1. Impact report, from the UI:** Lineage → **Impact analysis**. The modal has
Direction (both / downstream / upstream), Depth (1–5) and Evidence state
selects; changing any of them re-queries the API, which is the point — the
answer comes from persisted edges, not from the browser.

**2. Impact report, from the API:**

```bash
curl -s "http://127.0.0.1:8000/api/v1/assets/<asset_id>/downstream-impact?depth=3&direction=downstream&evidence_state=OBSERVED" \
  -H "Authorization: Bearer $TOKEN"
```

Expected keys: `direction`, `evidence_state`, `depth`, `total_affected`,
`state_counts`, and `levels[]` where each level has `depth`, `asset_count` and
`assets[]` with `state`, `coverage`, `evidence_sources` and the connecting
`edge_id`.

**3. Say the filter rule out loud:** filtering by a state hides the hops that do
not match *and stops traversal through them*, so an OBSERVED-only report does not
jump past a POSSIBLE hop to reach what sits behind it. An empty result is not
evidence that nothing depends on the asset.

**Presenter says:** *"POSSIBLE means declared but not proven for a run. UNKNOWN
means no evidence is stored — it is not proof of absence, and the product says so
in the report itself."*

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
| OpenLineage event becomes evidence | `tests/test_openlineage_ingest_service.py`, `tests/test_ingest_openlineage_route.py` |
| Coverage rules are versioned | `tests/test_lineage_coverage.py` (`kairos.coverage.v1`) |
| Impact respects depth, direction, state | `tests/test_impact_traversal.py` (6 tests) |
| One label per relationship, everywhere | `tests/test_catalog_read_model.py` |

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
| "606 offline tests pass, 85 skipped; 0 endpoint bodies verified against a DB in isolation" | "All tests pass" (unqualified) |

---

## What is NOT in the demo (be explicit if asked)

| Feature | Status |
|---|---|
| Deployed public URL | Live at `https://data-lineage-engine-5i2x.vercel.app` |
| `run_real()` experiment | Protocol filled; benchmark cases written; runner not yet wired |
| Automatic freshness scheduler | Not running — on-demand only |
| ProvSQL ground truth | Downgraded to ReferenceInterpreterProvider (RESEARCH_LOG.md R-01) |
| Playwright E2E | App-shell suite runs against Vite; signed-in sweep is manual |
| Quality assertions, glossary, domains | Implemented and verified against the deployed API |
| Notifications | Storage and UI implemented; empty until a scheduler emits an event |
