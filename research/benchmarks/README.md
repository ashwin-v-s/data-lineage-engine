# research/benchmarks

Benchmark case files for the Kairos lineage evaluation experiment.
Pack Section 21. `benchmark_version: v0.1-dev` (frozen when all cases committed).

Each file is a YAML case with: SQL, schema, expected static candidates,
ground-truth labels, and never-proves statements.

## Cases

| Case | SQL Construct | Split | Description |
|---|---|---|---|
| W01 | PROJECTION | development | Direct column copy |
| W02 | PROJECTION_ARITHMETIC | development | Arithmetic expression (two sources → one target) |
| W03 | CASE_WHEN | development | Conditional branch — the core research motif |
| W04 | AGGREGATE_SUM | development | SUM with GROUP BY |
| W05 | JOIN_INNER | development | INNER JOIN (two source tables) |
| W06 | AGGREGATE_COUNT_STAR | validation | COUNT(*) — no specific column dependency |
| W07 | WHERE_FILTER | validation | Filter column NOT in SELECT |
| W08 | COALESCE | validation | First non-null wins |
| W09 | SELECT_STAR | **held_out** | All columns projected |
| W10 | CASE_WHEN | **held_out** | CASE with value in all branches |

## Rules

- **DO NOT** tune on held_out cases (W09, W10).
- Ground truth is provided by `ReferenceInterpreterProvider` (human-derived,
  cross-checked by manual SQL trace). See `docs/RESEARCH_LOG.md` Entry R-01.
- `benchmark_version` must be frozen and committed before a real run starts.
- Fixture data in `contracts/fixtures/` is PLUMBING — it is not a benchmark case.
