# research/benchmarks

Benchmark case files for the Kairos lineage evaluation experiment.
Pack Section 21. `benchmark_version: v0.2-dev` (updated 2026-11-03 with NOT_PROPAGATED cases).

Each file is a YAML case with: SQL, schema, expected static candidates,
ground-truth labels, and never-proves statements.

## Cases

| Case | SQL Construct | Split | GT Labels | Description |
|---|---|---|---|---|
| W01 | PROJECTION | development | All PROPAGATED | Direct column copy |
| W02 | PROJECTION_ARITHMETIC | development | All PROPAGATED | Arithmetic expression |
| W03 | CASE_WHEN | development | All PROPAGATED | Conditional branch (US employees present) |
| W04 | AGGREGATE_SUM | development | All PROPAGATED | SUM with GROUP BY |
| W05 | JOIN_INNER | development | All PROPAGATED | INNER JOIN (matching rows) |
| W06 | AGGREGATE_COUNT_STAR | validation | All PROPAGATED | COUNT(*) |
| W07 | WHERE_FILTER | validation | All PROPAGATED | Filter column not in SELECT |
| W08 | COALESCE | validation | All PROPAGATED | First non-null wins |
| W09 | SELECT_STAR | **held_out** | All PROPAGATED | All columns projected |
| W10 | CASE_WHEN | **held_out** | All PROPAGATED | CASE with value in all branches |
| **W11** | CASE_WHEN | development | **NOT_PROPAGATED: salary** | No US employees — THEN branch never executes |
| **W12** | COALESCE | validation | **NOT_PROPAGATED: mobile, email** | All customers have phone — fallbacks never reached |
| **W13** | JOIN_INNER | validation | **NOT_PROPAGATED: all** | Empty join result — no matching rows |

## Rules

- **DO NOT** tune on held_out cases (W09, W10).
- W11–W13 are the NOT_PROPAGATED cases needed for K1/K3 evaluation.
- Ground truth is provided by `ReferenceInterpreterProvider` (human-derived,
  cross-checked by manual SQL trace). See `docs/RESEARCH_LOG.md` Entry R-01.
- `benchmark_version` must be frozen and committed before a real run starts.
- Fixture data in `contracts/fixtures/` is PLUMBING — not a benchmark case.
