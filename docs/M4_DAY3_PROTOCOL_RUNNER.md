# M4 Day 3 — Protocol Skeleton and Plumbing Runner

## 1. Protocol Structure

File: `research/protocol/v1.yaml`

The protocol skeleton follows the architecture pack Section 42 exactly.
Fields are marked with one of three statuses:

| Status | Meaning |
|---|---|
| LOCKED | Frozen by the architecture; changing requires a decision record |
| TBD | Awaits a team decision; blocks real execution until resolved |
| PLUMBING | Default for mock/fixture runs; not a research value |

Key sections:

```
protocol_version      1.0-skeleton
benchmark_version     TBD (frozen when benchmark cases are committed)
sql_subset            TBD (M1 confirms)
splits                TBD (D-07)
contribution_semantics TBD (D-11: where- vs why-provenance)
prediction_unit_universe TBD (D-12)

loss:
  mechanisms          [mcar, operator, dataset, branch, complete_run, correlated]
  levels              [0, 10, 30, 50, 70, 90]   ← LOCKED
  master_seed         TBD (D-04)
  replicates          TBD (D-04)
  rounding_rule       TBD (D-18; current impl uses int(round(n*p/100)))
  zero_arrival_semantics TBD (unresolved seam from D-09)

baselines             [B1, B2, B3, B4, B5]      ← LOCKED names
proposed              proposed

metrics:
  primary             TBD (D-05/D-08)
  secondary           [false_refutation, committed_accuracy, ...]
  confidence_interval TBD (D-08)
  na_rule             zero_denominator_is_NA     ← LOCKED (implemented)
  granularity_separation true                    ← LOCKED

aggregation           TBD (D-05)
stopping_rule         TBD (D-05)
exclusion_rules       TBD

ground_truth_isolation  true    ← LOCKED
no_gt_in_predictor      true    ← LOCKED
no_held_out_tuning      true    ← LOCKED

output_path           research/results/
```

---

## 2. TBD Blocking

File: `research/experiments/protocol_loader.py`

`validate_protocol(protocol)` checks 15 required-for-real-run fields for TBD
values and returns a `ProtocolValidationResult` listing every TBD field found.

`result.raise_if_blocking(plumbing=False)` raises `ProtocolBlockedError` if any
TBD fields remain and `plumbing` is False.  The error message names every TBD
field explicitly.

In plumbing mode (`plumbing=True`) the same TBD fields produce a warning to
stderr but do not block execution.

Required fields that block a real run:
```
benchmark_version, sql_subset, splits.development, splits.validation,
splits.held_out, contribution_semantics, prediction_unit_universe,
loss.master_seed, loss.replicates, loss.rounding_rule,
metrics.primary, metrics.confidence_interval,
aggregation, stopping_rule, exclusion_rules
```

YAML parser: minimal hand-written parser (standard library only, no PyYAML
dependency).  Supports `key: scalar`, `key: [inline, list]`, and nested
mappings via indentation.  Sufficient for v1.yaml's structure.

---

## 3. Plumbing vs Real Experiment

| Property | Plumbing mode (`--plumbing`) | Real mode |
|---|---|---|
| Data source | w03_case_when mock fixture | Real benchmark cases (not yet wired) |
| TBD fields | Permitted (warning only) | Blocked |
| Output label | `mode: PLUMBING` | `mode: REAL` |
| Research validity | NOT a research finding | Research finding (when all gates pass) |
| GT provider | `load_truth()` on mock fixture | Real GroundTruthProvider (M2, not yet wired) |

---

## 4. Runner Flow (`research/experiments/run.py`)

```
load_protocol(v1.yaml)
      ↓
validate_protocol()  → TBD check; block or warn
      ↓
[plumbing] load w03_case_when fixture (keys, static_ev, all_runtime_ev)
      ↓
[plumbing] build CaptureManifest (from instrumentation config, not from loss)
      ↓
mcar_loss(event_ids, level_pct, seed)
  → MCARResult (kept, removed, mask_hash)
  → surviving_runtime = [ev for ev in all_runtime_ev if ev.evidence_id in kept]
      ↓
_predict_all(keys, static_ev, surviving_runtime)
  → FourStateEngine.infer()
  → B1..B5 baselines
  → Dict[method_name → List[Prediction]]
      ↑
      |  ← GROUND TRUTH BOUNDARY: GT is not loaded until here ↓
      ↓
_load_ground_truth_after_prediction("w03_case_when")
  → Dict[DependencyKey → TruthLabel]
      ↓
_evaluate_all(predictions_by_method, truth)
  → evaluate() per method
      ↓
result_artifact(...)
  → mode, protocol_version, benchmark_version, loss_mechanism, loss_level,
    seed, mask_hash, gt_hash, prediction_hashes, git_sha, environment,
    tbd_fields_at_run_time, metrics, plumbing_notice
      ↓
_write_artifact(artifact, output_path)
  → research/results/result_plumbing_mcar{level}_seed{seed}.json
```

Entry point:
```
python research/experiments/run.py --protocol research/protocol/v1.yaml --plumbing [--loss-level N] [--seed N]
```

---

## 5. Ground-Truth Isolation

Three enforcement layers:

1. **Sequencing.** `_predict_all()` has no `truth` parameter. Its signature is
   `(keys, static_evidence, surviving_runtime) → Dict[str, List[Prediction]]`.
   Ground truth is loaded in a separate step that only runs after the prediction
   dict is complete.

2. **PredictorInput contract.** `PredictorInput` has no ground-truth fields.
   The test `test_predictors_never_receive_gt_object` asserts this at the
   dataclass level.

3. **Import boundary.** `research/reasoning/` and `research/baselines/` may
   not import `contracts.truth` or `research.ground_truth` (checked by
   `scripts/check_import_boundaries.py` in CI).

The runner imports `contracts.truth` only in the evaluation step and only to
call `load_truth()` and `evaluate()`.

---

## 6. Result Metadata

Every result artifact contains:

| Field | Source | Notes |
|---|---|---|
| `mode` | Runner | `PLUMBING` or `REAL` |
| `runner_version` | Hardcoded | `0.1.0-plumbing` |
| `protocol_version` | Protocol YAML | |
| `benchmark_version` | Protocol YAML | TBD in skeleton |
| `loss_mechanism` | Runner | `mcar` |
| `loss_level_pct` | CLI arg | |
| `seed` | CLI arg | |
| `mask_hash` | `_mask_hash()` from MCAR | SHA-256 of removed+level+seed |
| `ground_truth_hash` | `_gt_hash()` | SHA-256 of canonical GT mapping |
| `prediction_hashes` | `_prediction_hash()` per method | SHA-256 per method |
| `git_sha` | `git rev-parse --short HEAD` | `unavailable` if git not accessible |
| `environment.python_version` | `platform.python_version()` | |
| `environment.platform` | `platform.platform()` | |
| `tbd_fields_at_run_time` | `validate_protocol()` | Explicit record of what was TBD |
| `metrics` | `evaluate()` per method | Full confusion + all rates |
| `plumbing_notice` | Runner | Present and non-null in PLUMBING mode |

---

## 7. What Is Intentionally Not Yet Implemented

- Real benchmark cases (`research/benchmarks/` — M4+M1+M2)
- Real ground-truth provider wiring (M2 — ProvSQL or ReferenceInterpreter)
- Storage/PostgreSQL integration (M3)
- Other missingness mechanisms (operator, dataset, branch, complete_run, correlated)
- `protocol/v1.yaml` frozen field values (D-04, D-05, D-07, D-08, D-11, D-12, D-18)
- Zero-arrival semantics (unresolved seam)
- `run_real()` pipeline body
- Confidence intervals (D-08)
- Pilot experiment and kill-criteria evaluation
- Result interpretation document

---

## 8. Test Results

**Command:** `python -m pytest -q --ignore=tests/test_api_slice.py -p no:langsmith_plugin`

**Result:** 87 passed (62 pre-existing + 25 new protocol/runner tests)

**Import boundaries:** `import boundaries: ok`

**New tests (`tests/test_protocol_runner.py`, 25 tests):**

| Category | Tests |
|---|---|
| Protocol loads | `test_protocol_file_exists`, `test_protocol_loads_without_error`, `test_protocol_has_locked_loss_levels`, `test_protocol_has_all_baselines`, `test_protocol_integrity_flags_are_true` |
| TBD blocking | `test_validation_detects_tbd_fields`, `test_validation_lists_required_fields`, `test_tbd_fields_block_real_run`, `test_tbd_fields_do_not_block_plumbing`, `test_fully_resolved_protocol_passes_validation` |
| Plumbing runs | `test_plumbing_run_succeeds_with_tbd_protocol`, `test_plumbing_result_has_plumbing_notice` |
| GT sequencing | `test_gt_loaded_after_predictions`, `test_predictors_never_receive_gt_object`, `test_run_plumbing_predictions_contain_no_gt_fields` |
| Result mode | `test_result_mode_is_plumbing` |
| Result metadata | `test_result_has_required_metadata`, `test_result_has_metric_for_every_method`, `test_result_records_tbd_fields`, `test_result_records_loss_metadata` |
| Determinism | `test_plumbing_result_is_deterministic`, `test_different_seeds_can_differ`, `test_prediction_hash_helper_is_stable`, `test_gt_hash_helper_is_stable` |
| MCAR regression | `test_mcar_still_passes_post_runner` |
