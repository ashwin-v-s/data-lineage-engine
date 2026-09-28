# M4 Week 1 Checkpoint

> Status of this document: factual review of the repository as of Day 4.
> No results are claimed. No thresholds are invented.
> TBD protocol fields are expected and correct at this stage.

---

## 1. Completed Work

### Day 1 — Engine, Contracts, Baselines, Metrics Review

- Read and mapped all five engine rules R1–R5 against the architecture specification.
- Reviewed all shared contracts (`types.py`, `evidence.py`, `interfaces.py`, `truth.py`).
- Reviewed baselines B1–B5 for correctness and leakage.
- Reviewed `evaluate()` for correctness, NA handling, and D-12 implications.
- Performed R4 adversarial mutation test: mutation caught by 7 tests across 3 files.
- Identified architecture/code inconsistency AQ-1 (UNSUPPORTED + positive evidence).
- Identified open decisions D-09, D-10, D-12 as blockers for the full experiment.
- Created `docs/M4_DAY1_REVIEW.md`.
- Test count at end: **31 passed**.

### Day 2A — Engine Test Gaps

- Added 3 tests closing gaps identified in Day 1:
  - Empty `target_column_id` → R1 UNKNOWN
  - PARTIAL static + positive runtime → OBSERVED via R2
  - SUPPORTED + PARTIAL mix + complete negative evaluation → POSSIBLE via R4 (not REFUTED_FOR_RUN)
- Documented mixed-granularity gap as experiment-runner responsibility in `docs/M4_DAY2_TEST_GAPS.md`.
- No production code changed.
- Test count at end: **34 passed**.

### Day 2B — MCAR Simulator and Capture Manifest

- Resolved D-09 using the Capture Manifest approach.
- Implemented `research/missingness/mcar.py`: `mcar_loss()`, `MCARResult`, `_mask_hash()`.
- Implemented `research/missingness/capture_manifest.py`: `CaptureManifest`, `coverage_vector_for()`.
- 28 tests covering: loss fractions, determinism, disjoint/union, stable hash, manifest independence,
  no simulator-to-coverage leakage, zero-arrival seam documented as TBD.
- Created `docs/M4_DAY2_MCAR.md`.
- Test count at end: **62 passed**.

### Day 3 — Protocol Skeleton and Plumbing Runner

- Created `research/protocol/v1.yaml` following the Section 42 skeleton exactly.
  - LOCKED values marked LOCKED; unresolved decisions marked TBD.
  - 15 required-for-real-run fields explicitly TBD.
- Created `research/experiments/protocol_loader.py`:
  - Minimal standard-library YAML parser.
  - `validate_protocol()` lists every TBD field.
  - `raise_if_blocking()` blocks real runs; permits plumbing.
- Created `research/experiments/run.py`:
  - Full plumbing pipeline: load fixture → apply MCAR loss → predict → load GT → evaluate → write artifact.
  - GT loaded only after all predictions exist (enforced by function sequencing and parameter signature).
  - Result artifact contains: mode, protocol/benchmark version, loss level/seed/mask hash, GT hash,
    per-method prediction hashes, git SHA, environment, TBD field list, metrics, plumbing notice.
- Real mode raises `NotImplementedError` (benchmark + real GT not yet wired).
- 25 tests covering: protocol loading, TBD blocking, plumbing execution, GT sequencing,
  predictor isolation, result metadata, determinism.
- Created `docs/M4_DAY3_PROTOCOL_RUNNER.md`.
- Test count at end: **87 passed**.

---

## 2. Checkpoint Questions

These are the nine official questions from Pack Section 39.

---

### Q1 — Is ProvSQL feasible, or which fallback applies?

**Status: NOT M4 OWNED**

Evidence: This question is owned by M2 (Pack Section 39, row 1). M2 is responsible for the
ProvSQL spike report at `research/ground_truth/SPIKE_REPORT.md`. That file does not exist in
the repository. The `research/ground_truth/README.md` states the directory is M2's and lists
ProvSQL, ReferenceInterpreter, and the spike report as deliverables. No spike output has been
committed. M4 cannot answer this question and must not invent a fallback.

**Implication for M4:** Until M2 delivers a spike outcome, M4 cannot wire a real ground-truth
provider into the runner. The plumbing path (mock GT) is unaffected.

---

### Q2 — Does static extraction work on the intended SQL subset?

**Status: NOT M4 OWNED**

Evidence: This question is owned by M1 (Pack Section 39, row 2). Evidence required is corpus
tests passing and a construct support matrix in `ingestion/sql/SUPPORT_MATRIX.md`. Neither
the corpus nor the support matrix exists in the repository. The `ingestion/sql/` directory
contains only a README. M4 cannot answer this question.

**Implication for M4:** Until M1 delivers `StaticEvidence` for real benchmark cases, M4 uses
mock static evidence. The engine operates correctly on mocks (Q6 is READY). The real benchmark
path is blocked on M1.

---

### Q3 — Can runtime evidence be captured?

**Status: NOT M4 OWNED**

Evidence: This question is owned by M2 (Pack Section 39, row 3). Evidence required is an ETL
run, events preserved, and sample JSON. No ETL script, no events file, and no sample JSON exist
in `ingestion/openlineage/`. M4 cannot answer this question.

**Implication for M4:** Open decision D-10 (what counts as positive runtime evidence at column
level) is tied to this question and remains unresolved.

---

### Q4 — Is the evidence schema sufficient?

**Status: NOT M4 OWNED**

Evidence: This question is owned by M3 (Pack Section 39, row 4). Evidence required is sample
evidence stored via migration 0001. `backend/migrations/` contains no migration files. M4
reviews the evidence schema as a consumer only; the schema is PROVISIONAL and M3 has not yet
committed it. The current `contracts/evidence.py` defines `StaticEvidence` and `RuntimeEvidence`
at the contract level, which is sufficient for M4's mock-based work. Whether the PostgreSQL
schema (migration 0001) is sufficient is M3's determination.

**Implication for M4:** No immediate M4 blocker. Engine and runner operate on the contract-level
evidence objects; PostgreSQL wiring is a later integration step.

---

### Q5 — Does the bitemporal model work?

**Status: NOT M4 OWNED**

Evidence: This question is owned by M3. The four-row temporal example from Section 11 must be
reproduced by tests. No temporal tests exist under `tests/` that relate to the bitemporal model.
`backend/app/temporal/` referenced in the team guide does not exist. M4 is a consumer of temporal
context via `TemporalContext` in `DependencyKey`, but the temporal engine itself is M3's
responsibility.

**Implication for M4:** `TemporalContext` fields (`valid_at`, `known_as_of`) are present in
`DependencyKey` and are always `(None, None)` in current fixtures. Temporal filtering is
described as an upstream StorageRepository responsibility in the engine's R0 rule. No M4 blocker.

---

### Q6 — Can the reasoning engine operate on mocks?

**Status: READY**

Evidence: 17 tests in `tests/test_engine_rules.py` cover every rule (R1–R5) including:
- R1: unresolved identity (empty src, empty tgt), UNSUPPORTED static
- R2: positive evidence → OBSERVED, conflict flag, PARTIAL + positive → OBSERVED
- R3: complete negative evaluation → REFUTED_FOR_RUN, guards against PARTIAL and
  unsupported constructs, SUPPORTED+PARTIAL mix never refutes
- R4: missing evidence → POSSIBLE (the central safety property), confirmed by adversarial
  mutation (7 tests caught the R4→REFUTED mutation)
- R5: no static, no runtime → UNKNOWN
- Contract guards: incomplete coverage cannot be built, GT coverage mode rejected

Baselines B1–B5 tested in `tests/test_baselines.py` (5 tests).
Leakage tests in `tests/test_leakage.py` (4 tests).
Fixture plumbing in `tests/test_fixtures_plumbing.py` (4 tests).
Import boundaries: passing.

---

### Q7 — Is the experiment protocol executable?

**Status: READY**

Evidence:
- `research/protocol/v1.yaml` exists at the architecture-specified location.
- `python research/experiments/run.py --plumbing --loss-level 0 --seed 1` executes successfully,
  produces a JSON result artifact in `research/results/`, returns exit code 0.
- Protocol validation correctly identifies 15 TBD fields and blocks real execution
  (`ProtocolBlockedError` raised, exit code 1) while permitting plumbing mode.
- 25 tests in `tests/test_protocol_runner.py` cover: protocol loading, TBD blocking, GT
  sequencing, predictor isolation, result metadata completeness, determinism.
- The plumbing runner has been verified at loss levels 0, 30, and 50 with varying seeds.

---

### Q8 — Can the benchmark be generated?

**Status: PARTIAL**

Evidence: The benchmark format is defined at the contract level — `BenchmarkCase` in
`contracts/interfaces.py`, `DependencyKey` as the prediction unit, `StaticEvidence` and
`RuntimeEvidence` as the input types. The mock fixture `contracts/fixtures/w03_case_when.json`
demonstrates the format. However:

- No real benchmark case files exist in `research/benchmarks/`.
- `benchmark_version` and `sql_subset` in the protocol are TBD.
- Case splits (development/validation/held_out) are TBD (D-07).
- Real benchmark generation requires M1 (static extraction, supported SQL subset) and M2
  (runtime evidence capture, ground-truth provider). Neither has delivered yet.

PARTIAL because the format is defined and plumbing works, but real cases cannot be generated
without M1 and M2 deliverables.

---

### Q9 — Does the architecture need changes?

**Status: PARTIAL**

Evidence — open questions discovered during M4 Week 1 review:

| ID | Issue | Impact | Decision needed by |
|---|---|---|---|
| AQ-1 | UNSUPPORTED + positive evidence: engine returns UNKNOWN; architecture expanded table says OBSERVED. Code and doc disagree. | Changes R1 behavior and one test | Team before pilot |
| D-10 | Column-level OBSERVED requires column-level runtime evidence. OpenLineage is dataset-level. No enforcement exists. | Risk of false OBSERVED at column level | M2 with M4, Week 2 |
| D-12 | Prediction universe (static candidates + positive evidence pairs vs. full cross-product) not yet enforced. | Changes every metric denominator | M4 with M1, before pilot |
| D-18 | MCAR rounding rule: current impl uses `int(round(n*p/100))`. Must be confirmed before protocol commit. | Reproducibility of loss fractions | M4, before protocol commit |
| Zero-arrival | Manifest-covered scope + 0 surviving events: POSSIBLE or REFUTED_FOR_RUN? Not decided. | Affects R3 trigger rate | Team before real experiment |
| AQ-4 | Mixed-granularity inputs to `evaluate()` not guarded. Experiment runner must separate by granularity. | Metrics correctness | M4 when runner is built |

None of these require immediate contract changes. AQ-1 is the only one that affects
existing code (engine.py + one test); it should be resolved before the pilot.

---

## 3. Research Integrity Check

| Requirement | Status | Evidence |
|---|---|---|
| GT never enters prediction | SATISFIED | `PredictorInput` has no GT fields; `_predict_all()` has no `truth` parameter; import boundary enforced in CI; runtime `guard_inputs()` scans all inputs for GT tokens/types |
| GT loaded only after predictions | SATISFIED | `run_plumbing()` calls `_predict_all()` first, then `_load_ground_truth_after_prediction()`; test `test_gt_loaded_after_predictions` verifies function signatures |
| SQLGlot not used as GT | SATISFIED | No SQLGlot import exists anywhere in the codebase. GT types are in `contracts/truth.py` under the evaluation schema |
| MCAR removed-event info not used for CoverageVector | SATISFIED | `MCARResult` has no `coverage` field; `CaptureManifest.coverage_vector_for()` derives from instrumentation config, not from `removed`; test `test_coverage_vector_comes_from_manifest_not_simulator` verifies this |
| PLUMBING outputs clearly marked | SATISFIED | Result artifacts have `mode: PLUMBING` and `plumbing_notice` field explicitly stating "NOT research findings"; all mock data has `is_mock: True`; runner prints PLUMBING label to stdout |
| Real experiments blocked by TBD fields | SATISFIED | `validate_protocol()` + `raise_if_blocking(plumbing=False)` raises `ProtocolBlockedError` listing all 15 TBD fields; test `test_tbd_fields_block_real_run` verifies |
| No held-out tuning | SATISFIED | `no_held_out_tuning: true` in protocol; splits are TBD (not yet assigned so cannot be violated); runner does not currently accept benchmark cases |
| No invented thresholds | SATISFIED | Kill-criteria thresholds are TBD in the protocol; the checkpoint document makes no threshold claims |
| No invented research results | SATISFIED | No metric values from the plumbing run are presented as findings in any document; all fixture outputs are explicitly labelled PLUMBING |
| No unsupported claims of accuracy/novelty | SATISFIED | No performance claims are made anywhere in M4 documents; the architecture's PROVISIONAL label is retained throughout |

---

## 4. Test Status

**Command:**
```
python -m pytest -q --ignore=tests/test_api_slice.py -p no:langsmith_plugin
```

**Result: 87 passed, 0 failed**

| Test file | Tests | Scope |
|---|---|---|
| `test_engine_rules.py` | 17 | R1–R5 rules, contract guards, Day 2A gaps |
| `test_baselines.py` | 5 | B1–B5 behavior |
| `test_leakage.py` | 4 | GT isolation, import boundaries |
| `test_metrics.py` | 4 | Confusion matrix, rates, NA handling, query accuracy |
| `test_fixtures_plumbing.py` | 4 | Mock fixture end-to-end |
| `test_mcar.py` | 28 | Loss fractions, determinism, hash stability, manifest independence, leakage |
| `test_protocol_runner.py` | 25 | Protocol loading, TBD blocking, GT sequencing, result metadata |
| `test_api_slice.py` | — | Skipped (requires fastapi + httpx, not installed) |

**Import boundary check:**
```
python scripts/check_import_boundaries.py
→ import boundaries: ok
```

---

## 5. Remaining M4 Work

### A. Required before next phase (genuinely blocks moving forward)

1. **Resolve AQ-1** — UNSUPPORTED + positive evidence: engine returns UNKNOWN vs. architecture
   table says OBSERVED. Must be decided as a team; whichever answer is chosen, update engine.py
   and the corresponding test. This affects R1 behavior in the real benchmark.

2. **Resolve D-10 with M2** — define what runtime evidence at column level looks like and confirm
   its independence from the GT mechanism. Until resolved, OBSERVED at column level in real
   experiments has an unverified evidence basis.

3. **Resolve D-12 with M1** — define and enforce the prediction universe (static candidates +
   positive evidence pairs). The experiment runner must implement this before any metric from a
   real run is credible.

4. **Zero-arrival semantics** — decide what the runner produces when the manifest says a scope
   is covered but zero events survive MCAR loss. This directly affects the REFUTED_FOR_RUN rate
   and must be decided before a real experiment run.

5. **D-18 rounding rule** — confirm `int(round(n*p/100))` before the protocol commit. Small
   issue but required for reproducibility.

### B. Useful but not blocking

- Wire real `GroundTruthProvider` (M2 dependency) into the runner once the spike report is done.
- Add granularity separation to `run_plumbing()` / `run_real()` (AQ-4 — experiment runner
  responsibility documented in `docs/M4_DAY2_TEST_GAPS.md`).
- Add the five remaining missingness mechanisms (operator, dataset, branch, complete_run,
  correlated) — needed for the full experiment matrix, not for the pilot.
- Freeze `protocol/v1.yaml` remaining TBD fields (D-04, D-05, D-07, D-08, D-11) once team
  decisions are recorded.
- Add confidence intervals to `evaluate()` once D-08 is resolved.
- Add `test_experiment_runner.py` for granularity separation enforcement (noted in
  `docs/M4_DAY2_TEST_GAPS.md`).

### C. Owned by other members (M4 waits)

| Item | Owner | M4 dependency |
|---|---|---|
| ProvSQL spike / GT provider | M2 | Real GT wiring in `run_real()` |
| Static extraction, corpus, support matrix | M1 | Real `StaticEvidence` for benchmark cases |
| PostgreSQL migration 0001 | M3 | Storage integration |
| Bitemporal query correctness | M3 | Temporal context filtering (R0) |
| OpenLineage ETL and runtime evidence capture | M2 | Real `RuntimeEvidence` in benchmark |
| Benchmark case IDs and split assignment | M4+M1+M2 joint | `benchmark_version` unfreezing |

---

## 6. Week-1 Conclusion

**M4 is ready to proceed with documented dependencies.**

All M4-owned Week-1 deliverables are complete and tested:
- Engine rules R1–R5 reviewed, tested, and adversarially validated.
- Contracts, baselines, and metrics reviewed with no blocking defects found.
- MCAR simulator and Capture Manifest implemented with correct D-09 isolation.
- Protocol skeleton in place; TBD blocking enforced; plumbing runner executes end to end.
- Ground-truth isolation holds at three enforcement layers.
- 87 tests passing; import boundaries clean.

M4 is not blocked on its own deliverables.

M4 is waiting on M1 (static extraction), M2 (ProvSQL spike + runtime evidence capture), and
M3 (migration 0001 + temporal tests) before real benchmark cases, real GT, and real experiment
execution can proceed.

The TBD protocol fields are not a failure — they are intentionally unresolved architecture and
research decisions that the architecture document correctly defers to team consensus. The protocol
enforcement mechanism ensures these will be resolved before any real experiment result is produced.

**The next action for M4** is to resolve AQ-1 (UNSUPPORTED + positive evidence behavior) as a
team decision, and then — once M1 and M2 deliver their Week-1 outputs — begin wiring real
`StaticEvidence` and `RuntimeEvidence` into the runner and building the first real benchmark case
files. No experiment results should be reported until AQ-1, D-10, D-12, and zero-arrival
semantics are resolved.

> Execution-conditioned results are not yet validated. This checkpoint confirms the engineering
> foundation is in place; it does not confirm the research hypothesis.
