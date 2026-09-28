# M4 Day 2A — Unresolved Test Gaps

## Mixed-Granularity Handling in `evaluate()`

**Gap identifier:** AQ-4 (from Day 1 Review, Section 9)

**What was investigated.**

The Day 1 review identified that `research/metrics/metrics.py::evaluate()` does not enforce that all
predictions and truth records share the same `Granularity` level. If a caller passes a mix of
`Granularity.DATASET` and `Granularity.COLUMN` predictions together, they are scored as a single
pool.

The architecture document (Section 13, Section 15, LOCKED) states:

> Dataset lineage, column lineage and tuple or cell propagation are separate relations.
> Never score a dataset-level prediction against column-level truth.

**Why no test was added.**

The architecture imposes this as a constraint on the *caller* (the experiment runner), not on
`evaluate()` itself. Specifically:

1. `evaluate()` is a pure function: `Sequence[Prediction] × Mapping[DependencyKey, TruthLabel] → Dict`.
   Its contract does not include input validation beyond what Python's type system provides.
2. The architecture's separation rule is stated as an experiment-design constraint, not as a
   required exception or rejection behavior in the metrics function.
3. There is no existing code path in `evaluate()` that is supposed to raise, warn, or filter on
   granularity. Adding such behavior would be inventing a new contract, which is out of scope for
   Day 2A.
4. A test that asserts `evaluate()` does NOT raise on mixed granularity would document the current
   permissive behavior, but that is not a required contract property — it would just be testing
   that Python does not crash, which is not useful.

**What this means for Day 2 / experiment runner.**

When the experiment runner is built (later stage), it must:
- Separate predictions and truth records by `DependencyKey.granularity` before calling `evaluate()`.
- Call `evaluate()` once per granularity level.
- Never aggregate DATASET-level and COLUMN-level metrics into a single result.

Failure to do this would silently inflate or deflate all rates by mixing incompatible prediction
scopes. The architecture calls this out explicitly and it is LOCKED.

**Recommended test location when the experiment runner exists.**

Add a test in `tests/test_experiment_runner.py` (not yet created) that verifies the runner
separates granularity levels before calling `evaluate()`, and that it raises or warns if a mixed
batch is accidentally constructed.

**Status:** Open. Responsibility of the experiment runner. Not resolvable at the metrics layer
without inventing a new contract. Decision log entry recommended before experiment runner work
begins.
