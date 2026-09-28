# M4 Day 1 Review

## 1. Scope

Files inspected during this review:

- `docs/FINAL_ARCHITECTURE_AND_RESEARCH_EXECUTION_PACK.md` (Sections 1–15, 23–24, and the open-decisions appendix)
- `docs/TEAM_GUIDE.md` (all sections)
- `contracts/types.py`
- `contracts/evidence.py`
- `contracts/interfaces.py`
- `contracts/truth.py`
- `contracts/__init__.py`
- `contracts/mocks/loaders.py`
- `contracts/mocks/providers.py`
- `contracts/fixtures/w03_case_when.json`
- `contracts/fixtures/w03_case_when.truth.json`
- `research/reasoning/engine.py`
- `research/baselines/baselines.py`
- `research/metrics/metrics.py`
- `tests/test_engine_rules.py`
- `tests/test_baselines.py`
- `tests/test_leakage.py`
- `tests/test_metrics.py`
- `tests/test_fixtures_plumbing.py`
- `tests/helpers.py`
- `tests/conftest.py`
- `research/protocol/README.md`
- `scripts/check_import_boundaries.py`
- `scripts/make_fixtures.py`
- `pyproject.toml`

---

## 2. Repository State

No git branch was created for this review. All work was performed on the working tree as found. Branch: unknown at inspection time (no `git` commands run per instructions). Relevant existing components:

- Reasoning engine: `research/reasoning/engine.py` — present, version `0.1.0-plumbing`
- Baselines B1–B5: `research/baselines/baselines.py` — present
- Metrics: `research/metrics/metrics.py` — present
- Shared contracts: `contracts/` — present and frozen as foundation
- Tests: `tests/` — 31 tests passing (1 file skipped: `test_api_slice.py` requires FastAPI/httpx)
- Mock fixtures: `contracts/fixtures/w03_case_when.json` + `.truth.json` — present, labelled MOCK
- Protocol: `research/protocol/README.md` only — `v1.yaml` not yet written (expected, MVP-0 state)
- Loss simulator, experiment runner, benchmark cases, ground truth providers: not yet implemented (expected)

---

## 3. R1–R5 Rule Review

### R1 — Unresolved identity or unsupported static semantics → UNKNOWN

**Current behavior.** Fires when `key.source_column_id` or `key.target_column_id` is empty/falsy, OR when any static evidence record for the key has `parser_status == UNSUPPORTED`.

**Evidence consumed.** `DependencyKey` identity fields; `StaticEvidence.parser_status`; optionally the presence of positive runtime evidence (detected but not used — only appended to the explanation note).

**Output state.** `UNKNOWN`, rule_id `"R1"`.

**Concern: PARTIAL is not handled in R1.** The architecture's expanded rule table (Section 14) states: `Yes | PARTIAL, affected part unresolved | No | Any → POSSIBLE or UNKNOWN per R1`. The engine does NOT check for `PARTIAL` in R1. A `StaticEvidence` with `parser_status == PARTIAL` and no `unsupported_constructs` passes R1 and flows to R4 (POSSIBLE). This is the correct outcome when the dependency itself is resolved. However, the architecture note "per R1" implies that some PARTIAL cases should produce UNKNOWN. The exact boundary is not defined in the code, and there is no test for PARTIAL + positive evidence (should be OBSERVED per the expanded table row `Yes | SUPPORTED or PARTIAL | Yes | Any → OBSERVED`). Current code does produce OBSERVED in that case because R2 fires before R4, but there is no explicit test confirming it.

**Concern: positive runtime evidence is noted but silently discarded under R1.** When `parser_status == UNSUPPORTED` and positive runtime evidence exists, the architecture expanded table says the result should still be OBSERVED (`Yes | UNSUPPORTED | Yes | Any → OBSERVED`). The current engine explicitly does NOT override UNSUPPORTED with positive evidence — it returns UNKNOWN with a note. This is a deliberate design choice (the comment says "not used to override unsupported static semantics"), but it contradicts the expanded table in Section 14 of the architecture document. This is an open architecture question — the code and the document are inconsistent on this point, and the test `test_r1_unsupported_static_gives_unknown_even_with_positive_evidence` enshrines the current (possibly wrong) behavior.

**Rule ordering concern.** None for R1 — it is correctly the first rule to fire.

**Tests.** `test_r1_unsupported_static_gives_unknown_even_with_positive_evidence`, `test_r1_unresolved_identity_gives_unknown`.

---

### R2 — Positive runtime evidence → OBSERVED

**Current behavior.** Fires when there is at least one `RuntimeEvidence` record with `evidence_type == RUNTIME_POSITIVE` for the key's run/source/target/granularity signature.

**Evidence consumed.** `RuntimeEvidence` records with `RUNTIME_POSITIVE` type.

**Output state.** `OBSERVED`, rule_id `"R2"`. If no static candidate exists, a `CONFLICT_NO_STATIC_CANDIDATE` flag is added.

**Concerns.** None significant. The rule correctly fires before R3. Missing runtime evidence does not reach R2 (no record means no positive list). The conflict flag correctly records the case where runtime evidence exists without a static candidate.

**Open question (D-10).** OpenLineage events are typically dataset-level. OBSERVED at column level requires column-level evidence. The engine has no enforced granularity check between the incoming runtime evidence and the prediction key's granularity. If a dataset-level event is incorrectly mapped to a column-level key, R2 will fire and claim OBSERVED at column level without any column-level justification. This is a data quality / ingestion concern (M2's responsibility), but the engine has no guard against it.

**Tests.** `test_r2_positive_evidence_gives_observed`, `test_r2_positive_without_static_candidate_is_observed_with_conflict_flag`.

---

### R3 — Complete negative evaluation + fully supported static candidate → REFUTED_FOR_RUN

**Current behavior.** Fires when: `enable_refutation` is True; at least one `RUNTIME_NEGATIVE_EVALUATION` record exists whose `coverage.is_complete_for(key)` returns True; AND all static candidates have `parser_status == SUPPORTED` and no `unsupported_constructs`.

**Evidence consumed.** `RuntimeEvidence` with `RUNTIME_NEGATIVE_EVALUATION` type, filtered by `is_complete_for(key)`; `StaticEvidence` records (all must be SUPPORTED).

**Output state.** `REFUTED_FOR_RUN`, rule_id `"R3"`.

**`is_complete_for` check.** The method in `CoverageVector` checks: `run_covered`, `operator_covered`, `source_dataset_covered`, `target_dataset_covered`, `branches_covered`, `parser_status == SUPPORTED`, `coverage_mode == RUNTIME`, and that both `source_column_id` and `target_column_id` are in the respective covered-columns tuples. This is thorough and correctly enforced at the contract level (not just in the engine).

**Concerns.** The `RuntimeEvidence.__post_init__` already rejects a `RUNTIME_NEGATIVE_EVALUATION` with incomplete coverage, so a malformed negative evaluation cannot even be built. This is a strong guard.

**One potential gap.** The `fully_supported` check requires ALL static candidates to be SUPPORTED. A mixture of SUPPORTED and PARTIAL candidates causes `fully_supported = False` and the rule falls through to R4. This is correct behavior (conservative), but there is no test for this exact case (SUPPORTED + PARTIAL mix with a complete negative evaluation).

**Tests.** `test_r3_complete_negative_evaluation_gives_refuted`, `test_partial_static_never_refutes`, `test_static_with_unsupported_constructs_never_refutes`, `test_negative_evaluation_with_incomplete_coverage_cannot_even_be_built`, `test_negative_evaluation_with_structural_or_ground_truth_mode_cannot_be_built`.

---

### R4 — Static candidate, no positive evidence, no complete negative evaluation → POSSIBLE

**Current behavior.** Fires when at least one static candidate exists but neither R2 nor R3 conditions were met.

**Evidence consumed.** `StaticEvidence` records (any parser status that passed R1).

**Output state.** `POSSIBLE`, rule_id `"R4"`.

**Critical correctness.** This is the rule that prevents "no event" from becoming "did not happen". It is correctly implemented. When runtime evidence was lost or never captured, R4 returns POSSIBLE rather than REFUTED_FOR_RUN or UNKNOWN.

**Concerns.** None with the current implementation. The adversarial test below confirms its coverage.

**Tests.** `test_missing_runtime_evidence_never_refutes`, `test_partial_static_never_refutes` (implicitly tests R4 for PARTIAL), `test_static_with_unsupported_constructs_never_refutes` (R4 via PARTIAL path).

---

### R5 — No static candidate, no positive evidence → UNKNOWN

**Current behavior.** Catch-all. Fires when no static candidates exist and no positive runtime evidence exists.

**Evidence consumed.** Nothing (the absence of both static and runtime positive evidence).

**Output state.** `UNKNOWN`, rule_id `"R5"`.

**Concerns.** None. Correct fallback.

**Tests.** `test_r5_no_static_no_runtime_gives_unknown`.

---

## 4. Test Coverage Map

| Rule | Existing tests | What is verified | Missing cases |
|---|---|---|---|
| R1 (unsupported static) | `test_r1_unsupported_static_gives_unknown_even_with_positive_evidence` | UNSUPPORTED → UNKNOWN even with positive runtime evidence | No test for PARTIAL with positive evidence yielding OBSERVED (gap, but B4 test covers partially) |
| R1 (unresolved identity) | `test_r1_unresolved_identity_gives_unknown` | Empty source_column_id → UNKNOWN | No test for empty target_column_id alone |
| R2 (observed) | `test_r2_positive_evidence_gives_observed` | Positive evidence → OBSERVED, correct rule_id | No test for multiple positive evidence records |
| R2 (conflict flag) | `test_r2_positive_without_static_candidate_is_observed_with_conflict_flag` | Conflict flag set when no static candidate | — |
| R3 (refuted) | `test_r3_complete_negative_evaluation_gives_refuted` | Complete negative evaluation → REFUTED_FOR_RUN | No test for SUPPORTED + PARTIAL mix with complete negative evaluation (falls to R4, but not tested) |
| R3 (guards) | `test_partial_static_never_refutes`, `test_static_with_unsupported_constructs_never_refutes`, `test_refutation_disabled_is_three_state_b4` | PARTIAL/unsupported constructs block R3 | No test for the exact case: one SUPPORTED + one PARTIAL candidate with a valid negative evaluation |
| R4 (possible) | `test_missing_runtime_evidence_never_refutes` | Missing evidence → POSSIBLE, not refuted | No test for PARTIAL static with NO negative evaluation (currently flows to R4 correctly, untested directly) |
| R5 (unknown fallback) | `test_r5_no_static_no_runtime_gives_unknown` | No evidence → UNKNOWN | — |
| Contract guards | `test_negative_evaluation_with_incomplete_coverage_cannot_even_be_built`, `test_negative_evaluation_with_structural_or_ground_truth_mode_cannot_be_built`, `test_ground_truth_coverage_mode_on_positive_evidence_is_rejected_by_engine` | Contract-level validation, leakage rejection | — |
| Version + evidence IDs | `test_every_prediction_records_version_and_evidence` | Prediction metadata populated | — |

**Architecture/code inconsistency requiring a team decision:**
The architecture expanded table (Section 14) says `UNSUPPORTED + positive evidence → OBSERVED`. The engine currently returns UNKNOWN in that case. The test `test_r1_unsupported_static_gives_unknown_even_with_positive_evidence` locks in the engine's current (conflicting) behavior. Neither the test nor the code comment resolves the question authoritatively — both reflect the same choice but the architecture document says otherwise. This must be resolved as a team decision before the full experiment.

---

## 5. Adversarial Mutation Test

**Rule mutated.** R4 in `research/reasoning/engine.py`.

**Mutation applied.** Changed `PredictedState.POSSIBLE` to `PredictedState.REFUTED_FOR_RUN` in the R4 return statement. Rule_id was left as `"R4"` to make detection slightly harder.

**Expected failure.** `test_missing_runtime_evidence_never_refutes` (directly tests the R4 state).

**Actual result.** 7 tests failed, 24 passed.

**Tests that caught the mutation:**

1. `tests/test_engine_rules.py::test_missing_runtime_evidence_never_refutes` — directly asserts `(S.POSSIBLE, "R4")`
2. `tests/test_engine_rules.py::test_partial_static_never_refutes` — asserts PARTIAL → POSSIBLE
3. `tests/test_engine_rules.py::test_static_with_unsupported_constructs_never_refutes` — asserts constructs → POSSIBLE
4. `tests/test_engine_rules.py::test_refutation_disabled_is_three_state_b4` — B4 also hits R4 path
5. `tests/test_baselines.py::test_b4_three_state_never_refutes_and_respects_parser_status` — B4 wraps the engine, also caught
6. `tests/test_fixtures_plumbing.py::test_proposed_engine_states` — run_C and run_D fixture states are POSSIBLE
7. `tests/test_fixtures_plumbing.py::test_proposed_has_no_false_refutation_but_b2_does` — `false_refutation == 0.0` fails

**Test gap.** None: R4 mutation is well-caught by multiple tests across different test files. The test suite for R4 is adequate for the current rule definition.

**Confirmation.** Original code was restored immediately after the mutation test. Post-restore run: **31 passed, 0 failed**.

---

## 6. Contract Review

### Four states

The four states (`OBSERVED`, `REFUTED_FOR_RUN`, `POSSIBLE`, `UNKNOWN`) are defined in `contracts/types.py` as a `str, Enum`. They are correctly separated from ground-truth labels (`PROPAGATED`, `NOT_PROPAGATED`). The leakage scanner in the engine scans for truth token strings at runtime, which correctly prevents truth labels from reaching a predictor even if someone tries to pass them as strings.

### CoverageVector

`CoverageVector` is a structured, frozen dataclass — not a probability or confidence score, consistent with the architecture's explicit instruction. The `is_complete_for(key)` method enforces all required conditions: run coverage, operator coverage, dataset coverage, column coverage, branch coverage, `parser_status == SUPPORTED`, and `coverage_mode == RUNTIME`. The check is correct and the contract-level guard in `RuntimeEvidence.__post_init__` means that incomplete negative evaluations cannot be constructed at all, not just rejected at inference time.

**One gap:** `CoverageVector.parser_status` carries a `ParserStatus` value. This means the coverage vector embeds a parser-status assertion independently from `StaticEvidence.parser_status`. There is no contract or test that ensures these two are consistent for a given dependency. If a runtime provider emits a negative evaluation asserting `parser_status == SUPPORTED` while the static evidence says `PARTIAL`, R3 could in principle be reached if the engine trusted only the coverage vector's parser_status. Currently the engine checks `StaticEvidence.parser_status` separately in the `fully_supported` condition, so R3 correctly requires both to agree. This is not a bug, but it is an implicit coupling that is not tested.

### Parser status

`ParserStatus` (`SUPPORTED`, `PARTIAL`, `UNSUPPORTED`) is used correctly in both the contracts and the engine. The engine's R1 gate blocks UNSUPPORTED. PARTIAL flows through to R4 (POSSIBLE), which is conservative and correct. The architecture says PARTIAL cases "can never be refuted", and the engine respects this through the `fully_supported` check in R3.

**Unresolved question.** The architecture note about `PARTIAL + positive evidence → OBSERVED per the expanded table` implies R2 should fire for PARTIAL + positive. The engine does this correctly (R2 fires before the PARTIAL check in R3), but the test only covers the PARTIAL-no-refutation path, not the PARTIAL-observed path.

### Prediction units

`DependencyKey` is `(run_id, source_column_id, target_column_id, granularity, temporal_context)` — matches the architecture LOCKED definition exactly. The `temporal_context` field is present and propagated correctly, though `TemporalContext` is always `(None, None)` in the current fixtures (temporal filtering is described as upstream responsibility of the StorageRepository).

### Ground-truth isolation

Isolation is enforced at three layers:
1. `contracts/truth.py` is a separate module never imported by reasoning or baseline code.
2. `scripts/check_import_boundaries.py` enforces this via AST inspection (checked in CI and in `test_repository_import_boundaries_hold`).
3. The engine's `guard_inputs` / `_scan` function scans all inputs at runtime for truth tokens and truth-module types, raising `LeakageError`.

This is strong. The test `test_predictor_cannot_access_ground_truth` checks all three layers.

### Runtime vs. static evidence boundary

The architecture is clear: static evidence (SQLGlot/dbt) is "what could happen"; runtime evidence (OpenLineage) is "what was observed". Neither is ground truth. The code correctly represents this — `StaticEvidence` has no run_id, `RuntimeEvidence` has a run-scoped `DependencyKey`.

**Concern (D-10, open decision):** OpenLineage events are dataset-level. The engine accepts `RuntimeEvidence` at any granularity that its `DependencyKey` specifies. There is no enforcement that a column-level OBSERVED prediction requires column-level runtime evidence. If a dataset-level event is ingested and attached to a column-level key, the engine will claim OBSERVED at column level. The contract does not prevent this; it is ingestion-side responsibility. The consequence of getting this wrong is a false OBSERVED at column level — a "false observation" error. This is open decision D-10 and must be resolved before the experiment.

### Complete-negative evaluation

The contract is correct: the only path to `REFUTED_FOR_RUN` is an explicit `RUNTIME_NEGATIVE_EVALUATION` with a complete coverage vector. "No event" produces no row and no negative evaluation record. "Absence of an event is not evidence of absence" is enforced both at the contract level and in the engine. This is the central correctness property of the system and it holds.

### D-12: which prediction pairs are scored

The current `evaluate()` function scores all `(prediction, truth)` pairs where the key appears in both. Unscored predictions and unpredicted truth are counted and reported but not scored. The architecture says the prediction universe should be "static candidates plus pairs with positive runtime evidence" — the full cross-product would inflate results. Currently the experiment runner (not yet built) is responsible for constructing the key set; the engine just processes whatever keys are in `PredictorInput.keys`. Whether the key universe is constructed correctly is not enforced by any test or contract. This is open decision D-12.

---

## 7. Baseline Review

### B1 — Static-only

Uses only static evidence. Returns POSSIBLE for any key with a non-UNSUPPORTED static candidate; UNKNOWN otherwise. Runtime evidence is explicitly ignored. Correct for its stated purpose. No ground-truth leakage. No implementation concerns. Consistent with four-state vocabulary.

### B2 — Negative assumption

Positive runtime evidence → OBSERVED. Otherwise (including missing evidence) → REFUTED_FOR_RUN. This is the deliberately adversarial baseline that converts missing events into false refutations. Correctly implements the worst-case runtime-only behavior. No ground-truth leakage. Consistent with four-state vocabulary. The docstring correctly warns: "Do not claim it represents every real tool."

### B3 — Deterministic union

Positive runtime → OBSERVED; else any static candidate (parser status ignored) → POSSIBLE; else UNKNOWN. Notably, B3 does NOT consult parser_status on static evidence — this is intentional (it is the "naive union" baseline that ignores quality signals). Confirmed by test. No ground-truth leakage.

### B4 — Three-state (ablation)

Implemented as `FourStateEngine(enable_refutation=False)` — the proposed rules with REFUTED_FOR_RUN disabled. R4 replaces R3 whenever R3 would fire. Correct ablation design.

### B5 — Coverage-gated runtime only

Positive → OBSERVED; complete negative evaluation → REFUTED_FOR_RUN; otherwise UNKNOWN. No static evidence is consulted. Intended to isolate the value of static semantics. Correctly ignores static. No ground-truth leakage.

**Cross-cutting concern.** B3 ignores parser_status by design, but this makes it susceptible to claiming POSSIBLE for dependencies with UNSUPPORTED static semantics. This is the correct behavior for B3 (it is the "naive" baseline), but it should be clearly documented as an intentional feature rather than a defect when comparing against the proposed engine.

**No baseline appears to be a mock-only implementation.** All five have real logic. However, none has been validated against real data — all numbers computed against the current mock fixture are PLUMBING.

---

## 8. Metrics Review

### Current behavior

`evaluate()` takes `Sequence[Prediction]` and `Mapping[DependencyKey, TruthLabel]`. It computes:
- Confusion counts for all `(PredictedState, TruthLabel)` pairs
- Precision, recall, FPR, FNR in `strict` mode (OBSERVED only as positive) and `lenient` mode (OBSERVED + POSSIBLE as positive)
- `false_refutation`: `REFUTED_FOR_RUN` when truth is `PROPAGATED` — the central research metric
- `false_observation`: `OBSERVED` when truth is `NOT_PROPAGATED`
- `correct_refutation`: `REFUTED_FOR_RUN` when truth is `NOT_PROPAGATED`
- `committed_accuracy`, `wrong_commitment`, `non_committal`
- Query-answer accuracy (exact and Jaccard), grouping by `(run_id, target_column_id, granularity)`
- `unscored_predictions` and `unpredicted_truth` counts — these are reported, not silently ignored

Zero denominators return `NA` (None), never zero. Confirmed by test.

### D-12 implications

The `evaluate()` function is correct and impartial about which keys it scores — it scores whatever it receives. The responsibility for constructing the correct prediction universe (static candidates + positive-evidence pairs, as recommended in D-12) falls on the experiment runner, which is not yet built. The metrics function itself does not need to change for D-12; the experiment runner does.

**Missing units in prediction.** A prediction key not in truth is counted in `unscored_predictions`. This is reported but contributes 0 to all rates. This is correct behavior — if ground truth has no record for a key, we cannot evaluate it.

**Missing units in truth.** A truth key not in predictions is counted in `unpredicted_truth`. Again, reported but does not affect rates. This is the "static miss" case mentioned in D-12.

**No metric silently ignores anything.** All four states are represented in the confusion matrix. All NA cases are explicit.

**One structural gap.** The metrics do not enforce that all predictions are for the same granularity level. If a mix of DATASET and COLUMN level predictions is passed, they are scored together. The architecture says granularity levels must be scored separately. There is no guard against this in `evaluate()`. This is not a bug in `evaluate()` itself — it is a caller responsibility — but there is no test that verifies correct handling of mixed granularity.

---

## 9. Research/Architecture Questions

The following are unresolved open decisions from the architecture document. They are documented here, not resolved.

### D-09 — How the engine knows what evidence was lost

The engine must know the coverage of the capture layer to distinguish "evidence lost" from "truly not observed." The architecture proposes two approaches: (a) an instrumentation manifest, (b) event-integrity signals. Neither is implemented. The mock fixture sidesteps this by providing explicit coverage vectors in the fixture JSON. In a real experiment, the loss simulator must produce coverage vectors that reflect what a real system could know, not what was actually removed. This is the hardest correctness requirement in the entire research design.

**Question for the team:** who constructs the `CoverageVector` in the loss simulator — the simulator itself (based on what it removed), or the real capture layer (based on what it actually covered before loss)? If the simulator injects coverage vectors that reflect the true loss, it is not simulating real-world conditions. If it injects coverage vectors that reflect what the capture layer would have declared, the coverage must be defined by a model of the capture layer, not by the loss function.

### D-10 — What counts as positive runtime evidence

OpenLineage events are dataset-level by default. Column-level OBSERVED requires column-level evidence. The architecture acknowledges this is open. Until resolved, there is a risk that dataset-level events are incorrectly treated as column-level evidence in the benchmark, inflating OBSERVED counts and `committed_accuracy`. M2 must document what provider produces column-level evidence and verify its independence from the ground-truth mechanism.

### D-12 — Which prediction pairs are actually scored

The recommended default (static candidates + positive-evidence pairs) is not yet enforced anywhere in code. The experiment runner must implement this. Using the full cross-product of columns would report inflated correct results from trivial non-dependencies. The current fixture only contains 8 keys, so this issue does not manifest in the mock, but it is critical for the real experiment.

### Additional open questions discovered during review

**AQ-1 (R1 vs. expanded table inconsistency).** The engine returns UNKNOWN when `parser_status == UNSUPPORTED` even if positive runtime evidence exists. The architecture expanded table says this case should yield OBSERVED. The test `test_r1_unsupported_static_gives_unknown_even_with_positive_evidence` locks in the engine's behavior. This is a deliberate design choice in the code, but the architecture document says something different. The team must decide which is correct and update either the code or the architecture table before the experiment. If UNSUPPORTED + positive should be OBSERVED, this test must be inverted and R2 must fire before the UNSUPPORTED check in R1.

**AQ-2 (PARTIAL + positive evidence).** No test confirms that `PARTIAL` static + positive runtime evidence → OBSERVED. The architecture expanded table says it should. The engine does produce OBSERVED in this case (R2 fires before the fully_supported check in R3), but the gap in test coverage means a future refactor could break this silently.

**AQ-3 (CoverageVector.parser_status vs. StaticEvidence.parser_status consistency).** Two separate parser_status fields exist: one on the static evidence, one embedded in the runtime coverage vector. No contract ensures they agree. An inconsistency could create edge cases where R3's `fully_supported` check passes on static evidence but the coverage vector claims a different parser_status. Needs a team decision on whose parser_status is authoritative.

**AQ-4 (granularity separation in metrics).** `evaluate()` does not enforce that predictions and truth records are at the same granularity level. The architecture says dataset, column and tuple/cell predictions must be scored separately. No guard exists in the metrics layer; this must be enforced by the experiment runner.

**AQ-5 (kill criteria thresholds).** D-01 in the architecture is PENDING TEAM DECISION. No thresholds are defined. This must be decided before any full experiment run, per the architecture's own rule.

---

## 10. Changes Made

**No production code was changed during this review.**

The only temporary change was the adversarial mutation of R4 in `research/reasoning/engine.py` (Step 4). That mutation was reverted immediately after the test. The final state of `engine.py` is byte-for-byte identical to its state at the start of this review.

One file was created:
- `docs/M4_DAY1_REVIEW.md` — this document

---

## 11. Test Results

**Command:** `python -m pytest -q --ignore=tests/test_api_slice.py -p no:langsmith_plugin`

**Environment note:** A `langsmith` pytest plugin installed in the environment has a compatibility bug with Python 3.12 (`pydantic` v1 `ForwardRef._evaluate` signature change). It crashes before pytest can parse any flags. The workaround is `-p no:langsmith_plugin`. This is an environment issue unrelated to the project code; it should be documented in `docs/DECISION_LOG.md` and the CI configuration should explicitly exclude the plugin or pin `langsmith` to a compatible version.

**Result:** `31 passed in 0.47s`

**Skipped:** `tests/test_api_slice.py` (requires `fastapi` and `httpx`, neither installed in the current environment).

**Adversarial mutation result (R4 mutated to REFUTED_FOR_RUN):** `7 failed, 24 passed`. Original restored. Final re-run: `31 passed`.

---

## 12. Day 2 Readiness

The foundation contracts, engine, baselines, and metrics are sound. The following should happen before any experiment work begins.

**Team decisions required first (block the experiment):**
1. Resolve AQ-1: does UNSUPPORTED + positive evidence produce OBSERVED or UNKNOWN? Update either the engine or the architecture table and the corresponding test.
2. Resolve D-09: define exactly how the loss simulator produces `CoverageVector` objects without leaking knowledge of what was actually removed.
3. Resolve D-10: M2 must document which provider produces column-level runtime evidence and prove it is independent of the ground-truth mechanism.
4. Resolve D-12: the experiment runner must construct the key universe as "static candidates + positive-evidence pairs", not the full cross-product.
5. Resolve D-01: agree on kill-criteria thresholds before any full pilot run.

**Test gaps to close (M4 Day 2 tasks):**
- Add a test for PARTIAL static + positive evidence → OBSERVED (confirms R2 fires correctly before R3's fully_supported gate).
- Add a test for empty `target_column_id` alone in R1.
- Add a test for one SUPPORTED + one PARTIAL static candidate with a complete negative evaluation (should fall to R4, not R3).
- Add a test asserting that `evaluate()` rejects (or at least documents a warning for) mixed-granularity inputs.

**Day 2 should not start any of the following:** MCAR simulator, missingness mechanisms, `protocol/v1.yaml`, experiment runner, result writer, benchmark generation, pilot experiments, new baselines, new research metrics, threshold tuning, database integration, frontend changes, API changes.
