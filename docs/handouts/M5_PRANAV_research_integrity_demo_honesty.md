# Handout M5 — Pranav (`pranav-samal`) · Research Integrity, Findings & Demo Honesty

**Stream:** M5 — turn the research skeleton into measured findings, and make sure nothing in the product or the report claims more than a test or a query supports.
**You own:** `research/**` (protocol, benchmarks, missingness, experiments, metrics, baselines, ground truth), `tests/test_{engine_rules,mcar,protocol_runner,leakage,ground_truth_independence}.py`, `scripts/check_import_boundaries.py`, the evidence-state display language that M3/M4 render, E2E acceptance gates, `docs/DEMO_SCRIPT.md`, the results/findings chapter.
**Read first:** [FINAL_ARCHITECTURE_AND_RESEARCH_EXECUTION_PACK.md](../FINAL_ARCHITECTURE_AND_RESEARCH_EXECUTION_PACK.md) §14–§27, §42, §49 (still the binding contract) · [KAIROS_ARCHITECTURE_V2.md](../KAIROS_ARCHITECTURE_V2.md) §3 C1–C3 · [workstreams/M4_RESEARCH_INTEGRITY_AND_EVALUATION.md](../workstreams/M4_RESEARCH_INTEGRITY_AND_EVALUATION.md) · [PROJECT_STATUS_2026-11-02.md](../PROJECT_STATUS_2026-11-02.md) · **[VERIFICATION_2026-11-02.md](../VERIFICATION_2026-11-02.md) (what I executed today, with output — your gate design should start from §1, §4, §5)**

---

## 1. What you have already shipped (evidence)

- PR #4 `M4: complete Week 1 reasoning and experiment setup` (`6cad0a3`, in `main`).
- Four-state engine rules R1–R5 with `tests/test_engine_rules.py`; **MCAR loss simulator + capture manifest** (`research/missingness/{mcar.py,capture_manifest.py`) with the "coverage never derived from `MCARResult.removed`" invariant; `research/protocol/v1.yaml` with TBD gating (a real run refuses to start while a required field is TBD); `research/experiments/run.py` plumbing pipeline that loads truth **only after** predictions exist and hashes case/protocol/loss-mask/GT/prediction/git-SHA; baselines B1–B5 and metrics; the import-boundary + leakage guards.
- `docs/M4_DAY1_REVIEW.md` … `M4_WEEK1_CHECKPOINT.md`, `docs/BENCHMARK_RESULTS.md`, `research/results/*.json`.
- `12488f8` **M4 research integrity gate** (regression test + `docs/M4_TODAY_TEST_REPORT.md`) — merged into your local branch but **still unpushed**; `origin/feature/reasoning-experiments` is the only remote branch with work not in `main`.

## 2. What is **not** done — your gaps

| # | Gap | Proof |
|---|---|---|
| G1 | **There are no findings.** Every artifact in `research/results/` came from `--plumbing` against the 8-unit mock `w03_case_when` fixture; `docs/BENCHMARK_RESULTS.md` says so, and the only licensed claim is pipeline determinism + monotone recall erosion. Nothing answers RQ (§3 of the pack). | `run_plumbing()` vs `run_real()` |
| G2 | **Zero benchmark cases.** `research/benchmarks/` contains only `README.md` — no W01–W12 case files, no dev/validation/held-out split assignment (D-07), no frozen `benchmark_version`. | `ls` |
| G3 | **`run_real()` raises `NotImplementedError`** at [research/experiments/run.py:329](file:///E:/EDI-Metadata_Lineage/research/experiments/run.py#L329). The pipeline cannot execute a real experiment. | code |
| G4 | **`research/protocol/v1.yaml` still has 26 TBD occurrences**, i.e. seed, replicates, rounding, zero-arrival semantics, primary metric, CI method, aggregation, stopping rule, exclusion rules, sql_subset, contribution semantics (D-11), prediction-unit universe (D-12), environment fields. The gating you wrote is what is blocking you now. | `grep -c TBD` |
| G5 | **5 of 6 loss mechanisms are missing.** Only MCAR exists; operator-, dataset-, branch-, complete-run- and correlated-loss simulators are not implemented, so the levels 0/10/30/50/70/90 × 6 mechanisms matrix cannot run. | `research/missingness/` |
| G6 | **Kill criteria K1–K8 thresholds were never filled** ("[TEAM TO FILL]", D-01) and ablations (FULL-minus-{coverage,static,runtime,four-state,bitemporal}) have never been executed. | pack §26, §23 |
| G7 | **Ground truth is not machine-verified.** `GroundTruthProvider.determine` is abstract (`provider.py:36`); `research/ground_truth/SPIKE_REPORT.md` ends mid-SQL after 41 lines with no result/conclusion; the `ReferenceInterpreterProvider` fallback uses a human-supplied propagation map. Either close the spike (Docker/WSL2 ProvSQL) or state the downgrade explicitly in the report. | file |
| G8 | **Open semantic conflicts you own:** AQ-1 (engine returns `UNKNOWN` for UNSUPPORTED+positive while pack §14 says `OBSERVED` — a test now locks the conflict), D-09/D-10/D-12/D-18 undecided, zero-arrival semantics A/B/C/D undecided, AQ-4 mixed granularity deliberately untested pending a runner that does not exist. | `M4_DAY1_REVIEW.md` §4/§9, `M4_DAY2_MCAR.md` §7, `M4_DAY2_TEST_GAPS.md` |
| G9 | **Your integrity report is unreproducible on `main`.** `docs/M4_TODAY_TEST_REPORT.md` (line 15, table row 30) runs and passes `tests/test_api_slice.py` with 3 tests — that file was **deleted from `main` by `38d38ca`** ("replace obsolete mock API tests with fail-closed contract tests"), so your numbers came from the stale pre-delete branch. The report also quotes 84/92 totals where Day-2/Day-3 recorded 87, and `REPRODUCIBILITY.md`/`PROJECT_COMPLETION…` still quote 261/78 while the tree measures **346 passed / 80 skipped** today. | `git log --all -- tests/test_api_slice.py` |
| G10 | **Demo-honesty layer is incomplete.** `DataModeLabel` + `data-mode.test.js` exist only in the untracked tree, `app.js` still holds demo-fixture arrays, and there is no automated gate proving "a failed live call shows an error, not a fixture"; Playwright has one shell smoke spec and has never run against a deployed URL; `docs/DEMO_SCRIPT.md` does not exist. | `git status` |

## 2b. Executed today — defects that are **yours**, with the command that proved them

Evidence in [VERIFICATION_2026-11-02.md](../VERIFICATION_2026-11-02.md) §1, §4, §5. Your gates exist and pass; the problem is what they fail to notice.

| # | What I ran | What happened | Consequence |
|---|---|---|---|
| P1 | drove the running app in a browser, clicked all 22 nav entries | **exactly one API call** (`/api/v1/auth/config`) while the header claimed *"Views use records returned by the PostgreSQL catalog API"* | your "no fixture impersonates live data" gate did not catch this, because it tests `dataMode.js` as a **module**, not the rendered product |
| P2 | `npx playwright test` | 2 tests, both pass, and both assert only that the shell boots — the spec's own comment says it deliberately avoids auth and data ([shell.smoke.spec.js:6-11](file:///E:/EDI-Metadata_Lineage/frontend/e2e/shell.smoke.spec.js#L6-L11)) | the E2E acceptance gate is decorative. CI's `shell-smoke ✅` must never be quoted as evidence a screen works |
| P3 | `python scripts/db/check_migrations.py` | prints **`RESULT: PASS`** without contacting the database; the other four DB probes exit **0** on failure | a green "integrity" signal in CI is a static text comparison. Your boundary guard inherits that false confidence |
| P4 | `pytest --cov=backend.app` | **40 % total; 64 of 70 endpoint bodies never executed**; `tests/test_incidents.py` asserts only `422`s | "346 passed" is now a number you must qualify every time you print it. Recommend the wording: *"346 offline tests pass; 0 endpoint bodies verified against a database."* |
| P5 | `KAIROS_LIVE_API_TESTS=1 pytest` | no effect — the real gate is `KAIROS_TEST_USER_TOKEN` | any report line that says the live suite "can be enabled with `KAIROS_LIVE_API_TESTS=1`" is false today. M1 is fixing it; until then, do not print that claim |
| P6 | checked **your own** [REPRODUCIBILITY.md](../REPRODUCIBILITY.md) §4 "Contract Verification Matrix" against the served OpenAPI and the test file | 10 of the 12 routes it lists do not exist (`/api/v1/entities/…`, `/lineage/{id}/graph`, `/evidence/…`, `/evaluation/oracle/{run_id}`), and **none** of the 7 test functions it cites (`test_health`, `test_entity_endpoints`, `test_evidence_endpoints`, …) exist in `tests/test_api_v1.py` | a doc titled *Reproducibility Guide* is the single most quotable artifact in a viva, and it currently points an examiner at a deleted API generation. Retire §4 or regenerate it from [test_api_v1.py:129-157](file:///E:/EDI-Metadata_Lineage/tests/test_api_v1.py#L129-L157) |
| P7 | ran the documented verification entry point `python scripts/demo_m5.py` | prints `GET /api/v1/health -> 401` then dies: `KeyError: 'data'` at [demo_m5.py:27](file:///E:/EDI-Metadata_Lineage/scripts/demo_m5.py#L27) because it calls the non-existent `/api/v1/entities/orders_fact`. **Exit code 1** | the "run the demo" command in your guide cannot be run. Either point it at the real `/assets/...` surface or delete it and document the honest alternative (`pytest` + the browser tour) |
| P8 | read [BENCHMARK_RESULTS.md](../BENCHMARK_RESULTS.md) end to end | self-labels **PLUMBING ONLY**, lists all 15 TBD fields, pins `git_sha`/`mask_hash`/`runner_version`, and states in six numbered points why its numbers "must not be quoted as findings" | **this is the honesty standard for the rest of the repo** — keep it, and quote it as the pattern when M1's migration headers and your own §4 get rewritten. Your integrity work is real where it is written down; it is only the *automated* gates that are weak |
| P9 | read all four CI workflow files; delegated sweep of TEAM_GUIDE/workstreams/M* reports | **nothing in CI can fail on product dishonesty**: ci.yml runs the offline suite (40% coverage) + the static false-green `check_migrations.py`; e2e.yml's 2 tests assert only that the shell boots; live-smoke.yml points at a deployment that does not exist; and the docs sweep found **8 false claims in milestone docs** (worst: "No SQLGlot import exists anywhere" vs 13 files; "migrations dir contains no files"; a viva guide that says dbt parsing is PLANNED while it is implemented — a teammate following it would rebuild it) | add the false-green CI guard (probes vs wrong password must exit non-zero), the claim-vs-request browser test (P1), and re-date/verify the three stale milestone snapshots with an as-of-commit header | report §11b, §12

**Add to your gates (this is the actual work, not more unit tests):**
- **A browser-level honesty test.** Load the app, enter demo preview, click every nav entry, and fail if (a) any screen renders the words "catalog API" / "persisted" / "live" while zero authenticated data requests succeeded, or (b) more than one provenance banner is present. This is the test that would have caught P1 and the banner accumulation.
- **A claim-vs-request assertion:** for each of the seven demo screens, assert the specific endpoint it must have called, and record the response code. No call ⇒ the screen is `DEMO FIXTURE` and must say so.
- **A false-green guard:** a CI step that runs each `scripts/db/*` probe against a deliberately wrong password and asserts **non-zero exit**. A verification tool that cannot fail is not a verification tool.
- **Report wording:** replace every "tests pass" with the coverage-qualified sentence from P4, and cite [VERIFICATION_2026-11-02.md](../VERIFICATION_2026-11-02.md) as the source of the numbers.

## 3. What you need to do

**Wave 0**
1. Push `12488f8` + the merge and open the PR yourself (you have 1 merged PR in 6 weeks; M1 is fixing CODEOWNERS so it can be routed to you properly).
2. Re-measure and publish one authoritative test table (exact command, exact counts, environment) in `docs/REPRODUCIBILITY.md`, and annotate the three contradictory M4 reports as superseded rather than silently keeping both.

**Wave 1 — decisions, then cases**
3. Run the decision session the pack has been waiting for. `docs/DECISION_LOG.md` and `docs/RESEARCH_LOG.md` are mandated by `TEAM_GUIDE.md` but **have never been created** — create them, then record: D-01/K1–K8 thresholds, D-05 result classification + aggregation, D-07 splits, D-08 CI method, D-10 positive runtime evidence granularity, D-11 contribution semantics, D-12 prediction-unit universe, zero-arrival semantics, AQ-1 resolution (fix code or fix the §14 table — pick one and update the locking test).
4. Author the benchmark: 10–15 deterministic SQL cases (W01–W12 categories, the CASE-WHEN salary motif) as committed case files with expected static candidates, expected runtime observations, and independent ground-truth labels; freeze `benchmark_version` + hashes; assign dev/validation/held-out and **never** tune on held-out.
5. Get M2 to make ground truth resolvable for those cases (see their G12) and land the `evaluation`-schema / restricted-role enforcement so truth is physically unreadable from predictor code — then keep `test_ground_truth_independence.py` green in CI.

**Wave 2–3 — run the real experiment**
6. Implement the remaining five loss mechanisms against the capture manifest, each seeded, each recording removed-event hashes and mask hash, at levels 0/10/30/50/70/90.
7. Implement `run_real()`: protocol → case → apply loss → engine + B1–B5 → load truth **after** predictions → metrics (strict + lenient precision/recall, `false_refutation`, false_observation, UNKNOWN/POSSIBLE rates, correct/wrong commitment per CR-18, query-answer exact match + Jaccard, runtime/storage overhead) → artifact with all hashes.
8. Run the pilot (5 workloads × 3 loss levels × all baselines), then the full matrix + the five ablations; anything whose ablation equals a baseline does not count as independent evidence.
9. Write the findings: `docs/RESULTS_REPORT.md` with the table, the K1–K8 verdict (Supported / Inconclusive / Rejected), and an explicit limitations section (fixture-derived numbers quarantined, ProvSQL status, semi-automated truth if unresolved, mixed-granularity untested).

**Wave 4 — demo integrity gates (product-side, shared with M4)**
10. Freeze the evidence-state display language for M3/M4 (the four verbatim wordings; **the `High/Medium/Low` strength mapping and its derivation rule** per C1 — the stored `confidence` stays `null` and the API returns the label so no client invents a score; never a negative from absence) and add a test that fails if the UI renders `REFUTED_FOR_RUN` without run ID + complete coverage + negative-evaluation marker.
11. E2E acceptance gates in Playwright against the deployed URL: signup→import→read-back, label present on every screen, **forced API failure shows an error not a fixture**, no numeric confidence rendered, `source_mode` never hidden. Wire into `e2e.yml`.
12. `docs/DEMO_SCRIPT.md`: turn Architecture v2 **§10** into the runbook — the 12 numbered steps, the "what is demonstrably real" and "fails if" columns, the three sentences the presenter says out loud, and the honest-limits closing. Add a viva Q&A evidence table (claim → test/query/screenshot) and the pre-conditions checklist from §10 (DB auth green, migration status measured, deployed URL, `live-smoke` green) so nobody rehearses against a DB that is not reachable.
13. Keep the boundary guard: any product import of `research/ground_truth` must fail CI.
14. Own the **claim vocabulary** (checklist §16): approve the exact poster/report sentences, and veto anything the code has not been tested to do. Two phrasings are mandatory — *"scheduled freshness monitoring with event-driven updates where available"* (never "real-time monitoring" until an OpenLineage producer is genuinely connected and tested end to end) and *"Supabase-hosted PostgreSQL is our single authoritative store"* (never "Supabase automatically shares all data with all users"). Add the gate: **no slide, screen or report line may claim semantic search, grounded RAG, live lineage, or tenant isolation without a linked test or screenshot** — that is the spec's own demo-ready rule and it is checkable by grep on the deck.
15. Build the **fixture registry** with M4/M1 (v2 §11 D9): a queryable list of every `source_mode=DEMO_FIXTURE` provenance hash, so "no fixture impersonates live data" becomes an assertion instead of a promise. E2E should fail if any registry entry appears with a `LIVE` label, or if a fixture row is present in a workspace that never imported it.
16. Correct the record where the source spec is wrong about us (checklist §14): it claims quality tables, an embedding/trace schema, JSON lineage export, a deployed app and document/image ingestion all exist. None of them do. Keep `PROJECT_STATUS_2026-11-02.md` authoritative and make the report cite *that*, not the spec, for current state.

## 4. Definition of done (your gate)

`python scripts/run_benchmark_matrix.py` (or `run_real`) produces real artifacts with protocol/GT/prediction hashes and git SHA, `research/protocol/v1.yaml` has **zero** TBDs, K1–K8 has a verdict, the findings table exists with measured numbers and honest limitations, and the E2E gate proves no fixture ever impersonates live data on the deployed URL.

## 5. Do not

- Do not invent a TBD value to make the protocol look complete, do not change the protocol after seeing results, and do not tune on held-out cases.
- Do not present plumbing output (including `false_refutation 0.0 vs 0.5`, `committed_accuracy 1.0 vs 0.625`) as a research result — that is 8 made-up units.
- Do not add product features to make a claim true, and do not weaken a correct reasoning rule to fit a screen.
- Do not report an interrupted or skipped suite as passing; separate pass / fail / skipped / timed out / not run.

---

## 6. Full-project completion backlog — integrity & demo to 100 %

### Fix (broken today)
| # | Task | DoD |
|---|---|---|
| F1 | Gates missed P1-P8 because they test modules, not the product (report §14) | each gate has a product-level counterpart that would have caught it |
| F2 | Report wording everywhere: "346 offline tests pass; 0 endpoint bodies verified against a database" (P4); never quote `shell-smoke ✅` as screen evidence | no unqualified "tests pass" survives in docs you own |
| F3 | Re-date the three stale milestone snapshots (§11b): M1 viva guide, M4_TODAY, M4_WEEK1_CHECKPOINT — 8 false claims, incl. "No SQLGlot import exists" | every milestone doc carries as-of-commit header + corrected claims |

### Build (missing for 100 %)
| # | Task | DoD |
|---|---|---|
| B1 | **Browser honesty test**: load app, walk all nav, fail if any screen claims "catalog API/persisted/live" with zero authenticated calls, or >1 banner (P1) | test fails today, passes only when the shell is honest |
| B2 | **Claim-vs-request assertion** per demo screen: expected endpoint called or screen says DEMO FIXTURE (P1) | all 16 screens assert their contract |
| B3 | **False-green CI guard**: run each `scripts/db/*` probe against a wrong password, assert non-zero exit (P3) | CI step fails on any probe that cannot fail |
| B4 | **Coverage floor + governance-file tests**: CI fails below 45 %; create the missing `tests/test_governance*.py` with body-level (not 422-only) tests | floor enforced; incident ack/resolve bodies executed offline via fixtures |
| B5 | **Demo script** (v2 §9.2): every source with best-attainable state + never-proves sentence; fix/delete `demo_m5.py` (P7); retire REPRODUCIBILITY §4 (P6) | `python scripts/demo_m5.py` exits 0 and shows only real capability |
| B6 | **MLflow + RAG adapters co-own** (C1 #10/#11 with M2): you own the honesty contract of both (states, never-proves sentences, demo wiring) | both adapters ship with their honesty labels tested |
| B7 | **D12 memo**: where does the scheduler/evaluator actually run (serverless cron vs external worker) — written decision the whole team executes | one page, decision recorded, CI/config matches it |
