# M4 Day 2B — MCAR Simulator and Capture Manifest

## 1. MCAR Definition

MCAR = Missing Completely At Random.

Events are removed independently of event meaning, operator, dataset, branch, or
importance.  The probability that any given event is removed is the same for all
events.  This is the simplest loss mechanism and is used as the baseline
missingness condition in the experiment.

Loss levels (LOCKED, Pack Section 22): **0, 10, 30, 50, 70, 90 percent**.

---

## 2. D-09 Decision: Capture Manifest

**Decision:** Use Option 1 — Capture Manifest.

The architecture required resolving how the reasoning engine learns what was and was
not observed, without being told what the loss simulator removed beyond what a real
system could know (Pack Section 14, D-09).

**The adopted architecture is:**

```
Benchmark case
      ↓
CaptureManifest
  "What does the modelled capture layer cover?"
      ↓
All captured runtime events (before loss)
      ↓
MCAR simulator
  "Which events survive the random draw?"
      ↓
Remaining (surviving) events  +  CaptureManifest (unchanged)
      ↓
Caller assembles RuntimeEvidence for surviving events,
using manifest.coverage_vector_for() to attach CoverageVector
      ↓
ReasoningEngine → Predictions
```

The simulator only produces `MCARResult` (kept IDs, removed IDs, level, seed,
mask_hash).  It has no access to `CoverageVector` and produces no coverage
information.

---

## 3. Why the Simulator Cannot Generate CoverageVector

If the simulator told the engine which events it removed, the engine would know
exactly which scopes lost coverage.  This would allow the engine to derive a
"complete" negative evaluation for any scope with zero surviving events — even
though in a real system the capture layer would not know which events were lost to
transport/infrastructure failures.

Concretely: if the simulator injects `CoverageVector(run_covered=True, ...,
source_columns_covered=("salary",))` only for events it kept, then for events it
dropped it would effectively be encoding "we removed this" as "the capture layer
never covered this".  That leaks the simulator's removal decision into coverage,
making `REFUTED_FOR_RUN` systematically correct whenever the simulator removes
all events for a scope — which is circular.

**The invariant:** `CoverageVector` is always derived from `CaptureManifest`,
never from `MCARResult.removed`.

---

## 4. Data Flow (annotated)

```
CaptureManifest (built from benchmark instrumentation config, before loss)
  |
  |  manifest.coverage_vector_for(src, tgt)
  |   → CoverageVector (reflects what capture layer claims to cover)
  |
  v
RuntimeEvidence for all events (pre-loss, keyed by event_id)

  +---> MCAR simulator (mcar_loss(event_ids, level_pct, seed))
  |        → MCARResult.kept   (event IDs that survive)
  |        → MCARResult.removed (event IDs that are lost)   [never shown to engine]
  |        → MCARResult.mask_hash (for result artifact)
  |
  v
Subset: RuntimeEvidence for surviving events only
  (CoverageVector on each = from manifest, not from simulator)
  |
  v
ReasoningEngine.infer(PredictorInput)
  → Predictions (OBSERVED / REFUTED_FOR_RUN / POSSIBLE / UNKNOWN)

[Separately]
GroundTruthProvider → truth labels
truth + predictions → evaluate() → metrics
```

---

## 5. What Was Implemented

### `research/missingness/mcar.py`

- `mcar_loss(event_ids, level_pct, seed) → MCARResult`
  - Sorts event IDs before sampling (canonical ordering for determinism)
  - Removes `int(round(n * level_pct / 100))` events (see D-18 note below)
  - Uses `random.Random(seed)` — same inputs + same seed → identical result
  - Returns `MCARResult(kept, removed, level_pct, seed, mask_hash)`
- `MCARResult` — frozen dataclass; validates `level_pct ∈ {0,10,30,50,70,90}`
- `_mask_hash(removed, level_pct, seed) → str` — SHA-256 of canonical JSON
- `VALID_LEVELS = {0, 10, 30, 50, 70, 90}`

**D-18 note (rounding rule, PENDING full confirmation):** Current implementation
uses `int(round(n * level / 100))`, Python's banker's rounding.  D-18 is listed
as pending in the architecture document.  This choice must be confirmed before the
protocol commit and recorded in `docs/DECISION_LOG.md` when the team agrees.

### `research/missingness/capture_manifest.py`

- `CaptureManifest` — frozen dataclass
  - `run_id`, `instrumented_source_cols`, `instrumented_target_cols`
  - `operator_covered`, `source_dataset_covered`, `target_dataset_covered`,
    `branches_covered`, `parser_status`
  - `coverage_vector_for(src, tgt) → CoverageVector`
    - Reflects instrumentation config; `coverage_mode = CoverageMode.RUNTIME`
    - Returns a complete vector (all bools True, columns populated) if both
      columns are in the manifest; incomplete otherwise
  - `covers(src, tgt) → bool`
  - Does NOT contain: simulator removal set, ground truth, post-loss facts

---

## 6. Tests Added (`tests/test_mcar.py`, 28 tests)

| Category | Tests |
|---|---|
| 0% loss | `test_zero_loss_removes_nothing`, `test_zero_loss_kept_equals_input` |
| Loss level fraction | `test_loss_level_removes_correct_fraction[10/30/50/70/90]`, `test_90_percent_loss_leaves_expected_count` |
| Invalid level | `test_invalid_level_raises`, `test_mcar_result_rejects_invalid_level_directly` |
| Same seed determinism | `test_same_seed_same_result`, `test_same_seed_same_result_all_levels` |
| Different seed variation | `test_different_seeds_can_differ` |
| Disjoint / union | `test_kept_and_removed_disjoint`, `test_kept_union_removed_equals_input` |
| Sorted outputs | `test_outputs_are_sorted` |
| Stable hash | `test_mask_hash_is_stable`, `test_mask_hash_helper_directly`, `test_mask_hash_changes_with_different_removed/seed/level` |
| Manifest independence | `test_manifest_unchanged_across_loss_levels`, `test_manifest_is_immutable` |
| No simulator-to-coverage leakage | `test_coverage_vector_comes_from_manifest_not_simulator`, `test_manifest_coverage_vector_mode_is_runtime_not_ground_truth`, `test_manifest_coverage_vector_is_complete_for_covered_pair`, `test_manifest_coverage_vector_is_incomplete_for_uncovered_column` |
| Zero-arrival seam (TBD) | `test_zero_arrival_seam_is_tbd_not_asserted` |

---

## 7. Zero-Arrival Behavior — Unresolved (TBD)

**The situation:** The `CaptureManifest` says a `(source_col, target_col)` pair is
instrumented.  After the MCAR draw, zero events survive for that scope.

**The question:** What should the caller do when assembling `RuntimeEvidence`?

The options are:

| Option | Meaning | Implication |
|---|---|---|
| A | Produce no `RuntimeEvidence` at all for the scope | Engine sees no events → R4 (POSSIBLE) |
| B | Produce a `RUNTIME_NEGATIVE_EVALUATION` with a complete `CoverageVector` | Engine R3 → REFUTED_FOR_RUN if static is SUPPORTED |
| C | Produce a `RUNTIME_POSITIVE` with coverage | Would be wrong — no event was observed |
| D | Produce a partial coverage vector (dropping column coverage) | Engine R4 (POSSIBLE) |

Option B looks attractive if the manifest + zero arrivals = "we looked and saw nothing",
but it requires the caller to trust that zero arrivals means non-occurrence, not
just loss — which reintroduces the problem MCAR was meant to test.

**This question is NOT resolved here.**  The simulator and manifest are built to
be agnostic: the manifest faithfully records what was instrumented; the simulator
faithfully records what was removed.  The assembly step (manifest + surviving events
→ `RuntimeEvidence`) is where this decision must be encoded.

**Current state of the code:** `CaptureManifest.coverage_vector_for()` produces a
valid `CoverageVector` regardless of how many events survived.  It does not know
what the simulator removed.  A caller that wants to produce a negative evaluation
must decide this independently; the manifest alone cannot make that decision.

**Where to record the decision:** When the team resolves this, update:
- `research/missingness/capture_manifest.py` docstring
- `research/missingness/mcar.py` module docstring
- `tests/test_mcar.py::test_zero_arrival_seam_is_tbd_not_asserted` (replace TBD
  comment with a proper behavioral assertion)
- `docs/DECISION_LOG.md`

---

## 8. Intentionally NOT Implemented

- Other missingness mechanisms (operator loss, dataset loss, branch loss,
  correlated/burst loss) — Pack Section 22 lists six; only MCAR is here
- Protocol runner or experiment runner
- Benchmark generation
- Threshold tuning or kill criteria
- Database integration
- Ground-truth provider
- D-10, D-12, D-01 resolutions

---

## 9. Test Results

**Command:** `python -m pytest -q --ignore=tests/test_api_slice.py -p no:langsmith_plugin`

**Result:** 62 passed (34 pre-existing + 28 new MCAR tests)

**Import boundaries:** `import boundaries: ok`
