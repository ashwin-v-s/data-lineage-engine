# M4 — Research Integrity and Evaluation Gate

**Owner:** Person 4 · **Timebox:** 2–3 hours · **Architecture:** [`../KAIROS_FINAL_ARCHITECTURE.md`](../KAIROS_FINAL_ARCHITECTURE.md)

## Goal

Protect Kairos’ research claims and evidence semantics while product ingestion is expanded. Deliver a short, reproducible status of what currently passes and what remains untested; do not add product features. The product demo data path uses shared Supabase; this research workstream must not write research fixtures or ground truth into the shared product workspace.

## Inspect first

- `research/reasoning/`, `research/baselines/`, `research/ground_truth/`, `research/metrics/`
- `scripts/check_import_boundaries.py`
- `tests/test_engine_rules.py`, `test_leakage.py`, `test_ground_truth_independence.py`, `test_static_corpus.py`, `test_runtime_normalizer.py`
- `FINAL_ARCHITECTURE_AND_RESEARCH_EXECUTION_PACK.md` rules R0–R5 and leakage controls.

## Work

1. Re-run the focused research/contract test subset from a clean branch and save the exact command/results. Separately identify any API-suite hang/failure; do not count an interrupted full suite as passing.
2. Review that SQL/dbt declarations remain static, OpenLineage stays runtime evidence, and missing observations never imply `REFUTED_FOR_RUN`.
3. Add one regression test only for a confirmed semantic gap (unsupported input, incomplete coverage, or forbidden truth import). Do not rewrite correct rules just to fit a product screen.
4. Check import-boundary guard and ground-truth leakage tests. Report any mismatch between current implementation and research doc status labels.
5. Give M3/M5 precise display language for evidence classes and testable import diagnostics.

## Database boundary

Run the pure engine and leakage tests locally without a database where possible. If a research experiment specifically needs PostgreSQL/ProvSQL, use an isolated research database or dedicated Supabase project/branch, never the shared product project. Local Postgres is optional and only for that offline/research case; it is not the product source of truth.

## Likely files

- `tests/test_engine_rules.py`, `tests/test_leakage.py`, other focused tests as justified
- `docs/M4_*` only for evidence-backed status updates; do not edit product API/DB/UI.

## Acceptance

- Test report separates pass, fail, skipped, timed out, and not run.
- Four-state reasoning stays execution-conditioned and explanation-bearing.
- Ground-truth inputs/labels remain unavailable to predictors.
- No product demo claim is added without a test or runtime evidence.
