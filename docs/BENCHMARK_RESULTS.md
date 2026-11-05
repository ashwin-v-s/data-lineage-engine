# Kairos Benchmark Results — PLUMBING Evidence Only

## What was executed

The **existing plumbing-mode protocol runner** (`research/experiments/run.py`) was
driven across the full LOCKED MCAR loss-level matrix `{0, 10, 30, 50, 70, 90}` with
three distinct seeds `{1, 7, 42}` per level (18 cells), using
`research/protocol/v1.yaml` (protocol version `1.0-skeleton`). Every cell ran against the
**mock `w03_case_when` fixture** (`contracts/fixtures/w03_case_when.json`) — 8 dependency
units, 2 static evidence items, 4 runtime-evidence events — under the **MCAR** loss
mechanism, and was consolidated by `scripts/run_benchmark_matrix.py` into
`research/results/summary.json` and `research/results/summary.md`.

> ## ⚠️ THIS IS PLUMBING / PLUMBING-ONLY EVIDENCE — NOT A REAL BENCHMARK RESULT
>
> Every artifact carries the field
> `"plumbing_notice": "PLUMBING — outputs computed from mock fixture data. These numbers are NOT research findings."`
> and records the protocol fields that were still unresolved at run time in
> `tbd_fields_at_run_time` (**15 fields**, listed below). The numbers below are the output
> of a mock, fixture-level smoke pipeline. They are **not** a benchmark result, are **not**
> a research finding, and **must not** be quoted, cited, or reported as evidence about the
> Kairos method or any baseline. Real (non-plumbing) execution is blocked by the protocol
> validator while those TBD fields remain unresolved.

---

## Results tables

Values are **means over seeds `[1, 7, 42]`** per loss level; per-seed values and the
`mask_hash` / `ground_truth_hash` / `git_sha` for every artifact are in
`research/results/summary.json`. `NA` means the denominator was zero (the `na_rule`
`zero_denominator_is_NA` is LOCKED in the protocol and implemented in `research/metrics/metrics.py`).

### Loss level 0% — artifacts `result_plumbing_mcar0_seed{1,7,42}.json`

| method | false_refutation | false_observation | precision_strict | recall_strict | fpr_strict | fnr_strict | precision_lenient | recall_lenient | committed_accuracy | correct_commitment | non_committal | query_exact_strict | query_jaccard_strict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| proposed | 0.000 | 0.000 | 1.000 | 0.500 | 0.000 | 0.500 | 0.857 | 1.000 | 1.000 | 0.500 | 0.500 | 0.500 | 0.500 |
| B1 | 0.000 | 0.000 | NA | 0.000 | 0.000 | 1.000 | 0.750 | 1.000 | NA | 0.000 | 1.000 | 0.000 | 0.000 |
| B2 | 0.500 | 0.000 | 1.000 | 0.500 | 0.000 | 0.500 | 1.000 | 0.500 | 0.625 | 0.625 | 0.000 | 0.500 | 0.500 |
| B3 | 0.000 | 0.000 | 1.000 | 0.500 | 0.000 | 0.500 | 0.750 | 1.000 | 1.000 | 0.375 | 0.625 | 0.500 | 0.500 |
| B4 | 0.000 | 0.000 | 1.000 | 0.500 | 0.000 | 0.500 | 0.750 | 1.000 | 1.000 | 0.375 | 0.625 | 0.500 | 0.500 |
| B5 | 0.000 | 0.000 | 1.000 | 0.500 | 0.000 | 0.500 | 1.000 | 0.500 | 1.000 | 0.500 | 0.500 | 0.500 | 0.500 |

### Loss level 10% — artifacts `result_plumbing_mcar10_seed{1,7,42}.json`

| method | false_refutation | false_observation | precision_strict | recall_strict | fpr_strict | fnr_strict | precision_lenient | recall_lenient | committed_accuracy | correct_commitment | non_committal | query_exact_strict | query_jaccard_strict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| proposed | 0.000 | 0.000 | 1.000 | 0.500 | 0.000 | 0.500 | 0.857 | 1.000 | 1.000 | 0.500 | 0.500 | 0.500 | 0.500 |
| B1 | 0.000 | 0.000 | NA | 0.000 | 0.000 | 1.000 | 0.750 | 1.000 | NA | 0.000 | 1.000 | 0.000 | 0.000 |
| B2 | 0.500 | 0.000 | 1.000 | 0.500 | 0.000 | 0.500 | 1.000 | 0.500 | 0.625 | 0.625 | 0.000 | 0.500 | 0.500 |
| B3 | 0.000 | 0.000 | 1.000 | 0.500 | 0.000 | 0.500 | 0.750 | 1.000 | 1.000 | 0.375 | 0.625 | 0.500 | 0.500 |
| B4 | 0.000 | 0.000 | 1.000 | 0.500 | 0.000 | 0.500 | 0.750 | 1.000 | 1.000 | 0.375 | 0.625 | 0.500 | 0.500 |
| B5 | 0.000 | 0.000 | 1.000 | 0.500 | 0.000 | 0.500 | 1.000 | 0.500 | 1.000 | 0.500 | 0.500 | 0.500 | 0.500 |

### Loss level 30% — artifacts `result_plumbing_mcar30_seed{1,7,42}.json`

| method | false_refutation | false_observation | precision_strict | recall_strict | fpr_strict | fnr_strict | precision_lenient | recall_lenient | committed_accuracy | correct_commitment | non_committal | query_exact_strict | query_jaccard_strict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| proposed | 0.000 | 0.000 | 1.000 | 0.333 | 0.000 | 0.667 | 0.857 | 1.000 | 1.000 | 0.375 | 0.625 | 0.250 | 0.333 |
| B1 | 0.000 | 0.000 | NA | 0.000 | 0.000 | 1.000 | 0.750 | 1.000 | NA | 0.000 | 1.000 | 0.000 | 0.000 |
| B2 | 0.667 | 0.000 | 1.000 | 0.333 | 0.000 | 0.667 | 1.000 | 0.333 | 0.500 | 0.500 | 0.000 | 0.250 | 0.333 |
| B3 | 0.000 | 0.000 | 1.000 | 0.333 | 0.000 | 0.667 | 0.750 | 1.000 | 1.000 | 0.250 | 0.750 | 0.250 | 0.333 |
| B4 | 0.000 | 0.000 | 1.000 | 0.333 | 0.000 | 0.667 | 0.750 | 1.000 | 1.000 | 0.250 | 0.750 | 0.250 | 0.333 |
| B5 | 0.000 | 0.000 | 1.000 | 0.333 | 0.000 | 0.667 | 1.000 | 0.333 | 1.000 | 0.375 | 0.625 | 0.250 | 0.333 |

### Loss level 50% — artifacts `result_plumbing_mcar50_seed{1,7,42}.json`

| method | false_refutation | false_observation | precision_strict | recall_strict | fpr_strict | fnr_strict | precision_lenient | recall_lenient | committed_accuracy | correct_commitment | non_committal | query_exact_strict | query_jaccard_strict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| proposed | 0.000 | 0.000 | 1.000 | 0.222 | 0.000 | 0.778 | 0.821 | 1.000 | 1.000 | 0.250 | 0.750 | 0.083 | 0.208 |
| B1 | 0.000 | 0.000 | NA | 0.000 | 0.000 | 1.000 | 0.750 | 1.000 | NA | 0.000 | 1.000 | 0.000 | 0.000 |
| B2 | 0.778 | 0.000 | 1.000 | 0.222 | 0.000 | 0.778 | 1.000 | 0.222 | 0.417 | 0.417 | 0.000 | 0.083 | 0.208 |
| B3 | 0.000 | 0.000 | 1.000 | 0.222 | 0.000 | 0.778 | 0.750 | 1.000 | 1.000 | 0.167 | 0.833 | 0.083 | 0.208 |
| B4 | 0.000 | 0.000 | 1.000 | 0.222 | 0.000 | 0.778 | 0.750 | 1.000 | 1.000 | 0.167 | 0.833 | 0.083 | 0.208 |
| B5 | 0.000 | 0.000 | 1.000 | 0.222 | 0.000 | 0.778 | 1.000 | 0.222 | 1.000 | 0.250 | 0.750 | 0.083 | 0.208 |

### Loss level 70% — artifacts `result_plumbing_mcar70_seed{1,7,42}.json`

| method | false_refutation | false_observation | precision_strict | recall_strict | fpr_strict | fnr_strict | precision_lenient | recall_lenient | committed_accuracy | correct_commitment | non_committal | query_exact_strict | query_jaccard_strict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| proposed | 0.000 | 0.000 | 1.000 | 0.056 | 0.000 | 0.944 | 0.821 | 1.000 | 1.000 | 0.125 | 0.875 | 0.083 | 0.083 |
| B1 | 0.000 | 0.000 | NA | 0.000 | 0.000 | 1.000 | 0.750 | 1.000 | NA | 0.000 | 1.000 | 0.000 | 0.000 |
| B2 | 0.944 | 0.000 | 1.000 | 0.056 | 0.000 | 0.944 | 1.000 | 0.056 | 0.292 | 0.292 | 0.000 | 0.083 | 0.083 |
| B3 | 0.000 | 0.000 | 1.000 | 0.056 | 0.000 | 0.944 | 0.750 | 1.000 | 1.000 | 0.042 | 0.958 | 0.083 | 0.083 |
| B4 | 0.000 | 0.000 | 1.000 | 0.056 | 0.000 | 0.944 | 0.750 | 1.000 | 1.000 | 0.042 | 0.958 | 0.083 | 0.083 |
| B5 | 0.000 | 0.000 | 1.000 | 0.056 | 0.000 | 0.944 | 1.000 | 0.056 | 1.000 | 0.125 | 0.875 | 0.083 | 0.083 |

### Loss level 90% — artifacts `result_plumbing_mcar90_seed{1,7,42}.json`

| method | false_refutation | false_observation | precision_strict | recall_strict | fpr_strict | fnr_strict | precision_lenient | recall_lenient | committed_accuracy | correct_commitment | non_committal | query_exact_strict | query_jaccard_strict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| proposed | 0.000 | 0.000 | NA | 0.000 | 0.000 | 1.000 | 0.750 | 1.000 | NA | 0.000 | 1.000 | 0.000 | 0.000 |
| B1 | 0.000 | 0.000 | NA | 0.000 | 0.000 | 1.000 | 0.750 | 1.000 | NA | 0.000 | 1.000 | 0.000 | 0.000 |
| B2 | 1.000 | 0.000 | NA | 0.000 | 0.000 | 1.000 | NA | 0.000 | 0.250 | 0.250 | 0.000 | 0.000 | 0.000 |
| B3 | 0.000 | 0.000 | NA | 0.000 | 0.000 | 1.000 | 0.750 | 1.000 | NA | 0.000 | 1.000 | 0.000 | 0.000 |
| B4 | 0.000 | 0.000 | NA | 0.000 | 0.000 | 1.000 | 0.750 | 1.000 | NA | 0.000 | 1.000 | 0.000 | 0.000 |
| B5 | 0.000 | 0.000 | NA | 0.000 | 0.000 | 1.000 | NA | 0.000 | NA | 0.000 | 1.000 | 0.000 | 0.000 |

---

## Interpretation

### Why `false_refutation` is the headline metric

`false_refutation` is `n(REFUTED_FOR_RUN | PROPAGATED) / N_P`: the fraction of truly
propagating dependencies that the method wrongly declares as **definitely not propagating**
for the run. A refutation is the strongest, most operationally dangerous claim the system can
make — it tells an investigator "this edge does not exist / this input does not matter" — so a
false refutation is a silent, high-cost error. Precision, recall, and `committed_accuracy`
describe overall behaviour, but `false_refutation` isolates the specific failure mode the
research is designed to bound. In these tables, baseline **B2 refutes aggressively** and its
`false_refutation` climbs from `0.500` (0%) to `1.000` (90%) as the loss wipes out the
positive evidence, whereas the proposed method and the conservative baselines keep
`false_refutation` at `0.000`.

### What these numbers do and do NOT license

**Do:** they demonstrate that the plumbing pipeline is wired end-to-end and deterministic —
that every method is scored, that `NA` is emitted on zero denominators, that the MCAR mask
and ground-truth hashes are recorded, and that higher loss monotonically erodes recall
(`recall_strict` falls as the level rises) while aggressive refuters accumulate
`false_refutation`.

**Do NOT:** treat any number here as a finding about Kairos, about any baseline, or about the
loss/robustness relationship. Concretely, these numbers **cannot** be reported as research
results because:

1. **The data is a mock fixture**, not the benchmark. `w03_case_when` is a 8-unit,
   hand-built fixture flagged `"is_mock": true`; it is not a sample of the
   target population and contains no statistical power.
2. **The benchmark is unfrozen.** `benchmark_version`, the SQL subset, and the
   dev/validation/held-out splits are all TBD — there is no defined evaluation universe.
3. **The ground truth is a mock label file**, not a provider-derived oracle
   (ProvSQL / ReferenceInterpreter are not wired into the runner).
4. **The protocol is a skeleton** (`1.0-skeleton`); the primary metric, aggregation,
   stopping rule, and confidence-interval method are unresolved, so any "result
   classification" (Supported / Inconclusive / Rejected) is impossible.
5. **The headline metrics are provisional** (the metrics module states its definitions are
   provisional until the team confirms them).
6. **`run_real()` is not implemented**, so there is no real-mode pipeline to compare against.

### What remains blocked

- The **15 TBD protocol fields** (see below) — they block any non-plumbing run by design.
- **Real benchmark cases** (`research/benchmarks/` — M4+M1+M2).
- **Real ground-truth provider wiring** (M2 ProvSQL / ReferenceInterpreter).
- **The real-mode pipeline** (`run_real()` body) and storage/PostgreSQL integration (M3).
- The other five missingness mechanisms (operator, dataset, branch, complete_run, correlated)
  and the unresolved zero-arrival semantics.
- Confidence intervals (D-08) and the result-interpretation / stopping-rule machinery (D-05).

---

## Reproduction

From the repository root:

```bash
# Full matrix (6 loss levels x 3 seeds = 18 cells):
python scripts/run_benchmark_matrix.py

# A single cell, using the underlying runner directly:
python research/experiments/run.py --protocol research/protocol/v1.yaml --plumbing --loss-level 0 --seed 1
```

Each runner invocation writes
`research/results/result_plumbing_mcar{level}_seed{seed}.json`; the matrix script
consolidates every artifact into `research/results/summary.json` and
`research/results/summary.md`.

### Pinned environment (from the artifacts)

Taken verbatim from an artifact's `environment` and `git_sha` fields:

| Field | Value |
|---|---|
| `git_sha` | `7a12a34` |
| `environment.python_version` | `3.12.10` |
| `environment.platform` | `Windows-11-10.0.26300-SP0` |
| `protocol_version` | `1.0-skeleton` |
| `loss_mechanism` | `mcar` |
| `runner_version` | `0.1.0-plumbing` |

---

## Outstanding decisions that block a real run

Copied from the artifacts' `tbd_fields_at_run_time` (15 fields):

1. `benchmark_version` — freeze when benchmark cases are committed (M4+M1+M2).
2. `sql_subset` — the supported SQL constructs (M1 confirms).
3. `splits.development` — case IDs for the dev split (D-07).
4. `splits.validation` — case IDs for the validation split (D-07).
5. `splits.held_out` — case IDs for the held-out split (D-07).
6. `contribution_semantics` — where-provenance vs why-provenance (D-11).
7. `prediction_unit_universe` — static-candidates + positive-evidence pairs (D-12).
8. `loss.master_seed` — master seed for the loss draws (D-04).
9. `loss.replicates` — number of replicates (D-04).
10. `loss.rounding_rule` — rounding rule for the removal count (D-18); current
    implementation uses `int(round(n * level / 100))`.
11. `metrics.primary` — the team's primary metric (D-05 / D-08).
12. `metrics.confidence_interval` — bootstrap / Wilson / etc. (D-08).
13. `aggregation` — across cases / loss levels (D-05).
14. `stopping_rule` — Supported / Inconclusive / Rejected classification (D-05).
15. `exclusion_rules` — how unsupported cases are handled.

Additionally unresolved (referenced in the protocol/docs but not enumerated as
required-for-real-run fields): `loss.zero_arrival_semantics` (unresolved seam from D-09).
