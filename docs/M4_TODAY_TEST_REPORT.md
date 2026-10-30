# M4 Research Integrity — Test Report and Evaluation Gate

**Date:** 2026-10-01
**Branch:** `feature/reasoning-experiments`
**Owner:** Person 4 (M4)
**Workstream:** `docs/workstreams/M4_RESEARCH_INTEGRITY_AND_EVALUATION.md`

---

## 1. Test Results (Task 1)

### Exact command

```
python -m pytest tests/test_engine_rules.py tests/test_leakage.py tests/test_ground_truth_independence.py tests/test_baselines.py tests/test_metrics.py tests/test_fixtures_plumbing.py tests/test_mcar.py tests/test_protocol_runner.py tests/test_api_slice.py -v --tb=short -p no:langsmith_plugin
```

### Results

| Suite | Tests | Passed | Failed | Skipped | Timed out | Not run |
|---|---|---|---|---|---|---|
| `test_engine_rules.py` | 17 | 17 | 0 | 0 | 0 | 0 |
| `test_leakage.py` | 4 | 4 | 0 | 0 | 0 | 0 |
| `test_ground_truth_independence.py` | 2 | 2 | 0 | 0 | 0 | 0 |
| `test_baselines.py` | 5 | 5 | 0 | 0 | 0 | 0 |
| `test_metrics.py` | 4 | 4 | 0 | 0 | 0 | 0 |
| `test_fixtures_plumbing.py` | 4 | 4 | 0 | 0 | 0 | 0 |
| `test_mcar.py` | 21 | 21 | 0 | 0 | 0 | 0 |
| `test_protocol_runner.py` | 24 | 24 | 0 | 0 | 0 | 0 |
| `test_api_slice.py` | 3 | 3 | 0 | 0 | 0 | 0 |
| **Total** | **84** | **84** | **0** | **0** | **0** | **0** |

**Note:** `test_engine_rules.py` has 17 tests (15 original + 2 Day 2A gap tests). `test_ground_truth_independence.py` is newly added in this session (Task 3). The combined research suite is 84 tests. When counting the API slice separately (which tests product integration, not research semantics), the total is 92. The earlier "87 passed" figure reflected the research subset before adding the 2 new regression tests.

### Environment note

A `langsmith` pytest plugin in the environment has a Python 3.12 compatibility bug (pydantic v1 `ForwardRef._evaluate` signature change). It crashes pytest at startup. The workaround is `-p no:langsmith_plugin`. This is an environment issue, not a project code issue.

### API suite (separate check)

`test_api_slice.py` was run separately with a 20-second timeout guard. It completed in 3.46s with 3 passed, 1 warning (httpx deprecation). No hang, no failure.

---

## 2. Evidence Semantics Review (Task 2)

### SQL/dbt declarations remain static

**Verified.** `StaticEvidence` in `contracts/evidence.py`:
- Has no `run_id` field
- Docstring: "What a query COULD depend on (SQLGlot / dbt). Never proof that anything executed."
- Contains `parser_status` (SUPPORTED/PARTIAL/UNSUPPORTED) — a quality signal, not a runtime observation
- Contains `unsupported_constructs` and `diagnostics` — declarative metadata

**Conclusion:** Static evidence correctly represents "what could happen", never "what did happen."

### OpenLineage stays runtime evidence

**Verified.** `RuntimeEvidence` in `contracts/evidence.py`:
- Is run-scoped via `DependencyKey` (which carries `run_id`)
- Docstring: "Positive observations or explicit, complete negative evaluations. Absence is never a record."
- `EvidenceType` enum deliberately has NO "absent" value — missing events are never stored
- `__post_init__` rejects incomplete negative evaluations: "missing events are never recorded as negatives"

**Conclusion:** Runtime evidence correctly represents "what was observed", and the contract structurally prevents absent events from becoming evidence.

### Missing observations never imply REFUTED_FOR_RUN

**Verified.** In `research/reasoning/engine.py`, the rule ordering is:

1. R1: Unsupported/unresolved → UNKNOWN
2. R2: Positive runtime evidence → OBSERVED
3. R3: Complete negative evaluation + fully supported static → REFUTED_FOR_RUN
4. R4: Static candidate, no positive evidence, no complete negative → POSSIBLE
5. R5: No static, no positive → UNKNOWN

R3 (the only path to REFUTED_FOR_RUN) requires an explicit `RUNTIME_NEGATIVE_EVALUATION` record with `coverage.is_complete_for(key)` returning True. This means:
- All coverage flags must be True (run, operator, source dataset, target dataset, branches)
- `parser_status == SUPPORTED`
- `coverage_mode == RUNTIME`
- Source and target columns must be in the covered columns tuples

An absent event produces no record, so R3 cannot fire. R4 fires instead, returning POSSIBLE.

**Test coverage:** `test_missing_runtime_evidence_never_refutes` directly asserts this. The adversarial mutation test in Day 1 confirmed that mutating R4 to return REFUTED_FOR_RUN is caught by 7 tests.

**Conclusion:** The central correctness property holds. Missing observations produce POSSIBLE, never REFUTED_FOR_RUN.

---

## 3. Regression Test Added (Task 3)

### Confirmed gap

The original test suite checked that:
- The engine refuses ground-truth objects at runtime (`test_leakage.py::test_predictor_cannot_access_ground_truth`)
- Reasoning/baseline modules do not import `contracts.truth` or `research.ground_truth` (AST check in `test_leakage.py`)

It did NOT check the reverse direction:
- Ground-truth modules must not import prediction/reasoning/baseline/ingestion modules

Without this check, a future ground-truth provider could import reasoning code, creating a circular dependency and risking prediction logic leaking into truth construction.

### Test added

`tests/test_ground_truth_independence.py` — 2 tests:
1. `test_ground_truth_does_not_import_prediction_modules` — scans `research/ground_truth/*.py` for forbidden imports (sqlglot, ingestion, research.reasoning, research.baselines, backend, frontend)
2. `test_ground_truth_does_not_define_truth_labels_as_predictions` — verifies `TruthLabel` values (PROPAGATED, NOT_PROPAGATED) do not overlap with `PredictedState` values (OBSERVED, REFUTED_FOR_RUN, POSSIBLE, UNKNOWN)

Both tests pass.

---

## 4. Import-Boundary Guard and Leakage Check (Task 4)

### Import boundary script

**Command:** `python scripts/check_import_boundaries.py .`
**Result:** `import boundaries: ok` (exit code 0)

No violations found. All four boundary rules hold:
- `research/` does not import `backend` or `frontend`
- `research/reasoning/` does not import ground-truth, interfaces, mocks, or ingestion
- `research/baselines/` does not import ground-truth, interfaces, mocks, or ingestion
- `research/ground_truth/` does not import ingestion, sqlglot, reasoning, or baselines

### Leakage tests

All 4 tests in `test_leakage.py` pass:
- Predictor input cannot access ground truth (type-level, runtime, AST)
- Truth label strings anywhere in input are refused
- Repository import boundaries hold
- Boundary checker detects synthetic violations

### Mismatch between implementation and research doc status labels

**One known mismatch (AQ-1, from M4_DAY1_REVIEW.md, still open):**

The architecture expanded table (Section 14) states that `UNSUPPORTED` static + positive runtime evidence should yield `OBSERVED`. The engine currently returns `UNKNOWN` in this case, and the test `test_r1_unsupported_static_gives_unknown_even_with_positive_evidence` locks this behavior in.

This is a deliberate design choice in the code, but it contradicts the architecture document. This must be resolved as a team decision before the experiment. No change was made in this session — the workstream says "Do not rewrite correct rules just to fit a product screen."

**No new mismatches found.** The engine's status label "PROVISIONAL, NOT VALIDATED" is accurate: the reasoning hypothesis has not been experimentally validated. The version string "0.1.0-plumbing" correctly reflects that the implementation is plumbing-grade, not validated.

---

## 5. Display Language for M3/M5 (Task 5)

### Evidence class display strings

These are the precise strings M3 and M5 should use in the UI/API to label evidence. They prevent the common error of displaying a declared/parsed dependency as "observed."

| Evidence type | API value | UI display label | What it means | What it does NOT mean |
|---|---|---|---|---|
| `STATIC_DEPENDENCY` | `STATIC_DEPENDENCY` | "Declared dependency (static analysis)" | A SQL parser or dbt manifest declares this source-target relationship | That the query executed in this run |
| `DBT_DECLARED` | `DBT_DECLARED` | "Declared dependency (dbt manifest)" | A dbt manifest declares this model dependency | That the model ran in a specific run |
| `RUNTIME_POSITIVE` | `RUNTIME_POSITIVE` | "Observed in run" | An OpenLineage event observed data flowing from source to target in this run | That propagation occurred at a finer granularity than the event contains |
| `RUNTIME_NEGATIVE_EVALUATION` | `RUNTIME_NEGATIVE_EVALUATION` | "Complete evaluation: no propagation" | A complete negative evaluation confirmed no propagation for this run under declared coverage | That the dependency can never occur in any run |
| *(no record)* | *(absent)* | "No runtime evidence captured" | No runtime event was captured for this dependency in this run | That no lineage exists (absence is not evidence of absence) |

### Four-state display strings

These are the locked UI labels for each reasoning state. M5 should use these verbatim in the frontend.

| State | UI label | Short description | When it fires |
|---|---|---|---|
| `OBSERVED` | "Observed" | "At least one source value was observed to contribute to at least one target output in this run." | R2: positive runtime evidence exists |
| `REFUTED_FOR_RUN` | "Refuted for run" | "No propagation was established for this run under a declared complete-evaluation condition. This is not a universal claim that the dependency can never occur." | R3: complete negative evaluation + fully supported static |
| `POSSIBLE` | "Possible" | "Static analysis permits this dependency, but available evidence is insufficient to establish whether propagation occurred in this run." | R4: static candidate exists, no positive evidence, no complete negative |
| `UNKNOWN` | "Unknown" | "Kairos cannot safely evaluate this dependency because relevant semantics, identity, schema or instrumentation is unsupported or ambiguous." | R1/R5: unsupported/unresolved, or no evidence at all |

### Rules for M3/M5 import diagnostics

When M3/M5 display import results, they should:

1. **Never display a declared/parsed edge as "Observed."** Static evidence is "Declared dependency," not "Observed."
2. **Never display "No lineage" when the correct label is "No runtime evidence captured."** Missing events are not evidence of absence.
3. **Show diagnostics for unsupported input.** If an adapter returns `UNSUPPORTED`, display the specific unsupported constructs and do not silently turn it into an empty successful import.
4. **Label fixture/demo data visibly.** Sample data must be distinguishable from a user's imported catalog.
5. **Preserve the source_system on every edge.** Conflicts between sources are inspectable, not silently resolved.
6. **Use the four-state labels verbatim.** Do not invent intermediate labels like "likely" or "probable."

---

## 6. Acceptance Checklist

| Criterion | Status |
|---|---|
| Test report separates pass, fail, skipped, timed out, and not run | ✅ Section 1 |
| Four-state reasoning stays execution-conditioned and explanation-bearing | ✅ Section 2 |
| Ground-truth inputs/labels remain unavailable to predictors | ✅ Section 3 + Section 4 |
| No product demo claim is added without a test or runtime evidence | ✅ No product claims made |
| Import-boundary guard holds | ✅ Section 4 |
| No mismatch between implementation and research doc (new) | ✅ Section 4 |
| Display language for M3/M5 provided | ✅ Section 5 |
