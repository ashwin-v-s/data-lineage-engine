# Kairos: data lineage & metadata engine (research prototype)

Bitemporal lineage infrastructure plus a **provisional** research layer: coverage-aware, execution-conditioned
reasoning over static lineage and incomplete runtime evidence. The full design is in
[`docs/FINAL_ARCHITECTURE_AND_RESEARCH_EXECUTION_PACK.md`](docs/FINAL_ARCHITECTURE_AND_RESEARCH_EXECUTION_PACK.md). Read it first.

## What exists today

| Area | Status |
|---|---|
| `backend/app/main.py` tiny FastAPI slice on mock data | IMPLEMENTED (PLUMBING), needs `pip install fastapi httpx` |
| `contracts/` shared types, Protocols, mocks, fixtures | IMPLEMENTED (PROVISIONAL, freeze at architecture freeze) |
| Reasoning engine, rules R1 to R5 (`research/reasoning`) | IMPLEMENTED on mocks, NOT VALIDATED |
| Baselines B1 to B5 (`research/baselines`) | IMPLEMENTED on mocks, NOT VALIDATED |
| Metrics (`research/metrics`) | IMPLEMENTED, unit-tested against hand-computed counts |
| Leakage guards and import-boundary checker | IMPLEMENTED |
| Ground truth (ProvSQL spike, providers), SQLGlot adapter, ETL, migrations, temporal queries, API, UI, loss simulator, runner | NOT IMPLEMENTED |
| Any experiment result | NOT YET MEASURED. The fixture is illustrative PLUMBING, not data. |

**New here? Read [`docs/TEAM_GUIDE.md`](docs/TEAM_GUIDE.md)** for what is in this repo, how to start, and what each member does next.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate      # Python 3.11+
pip install pytest
python scripts/check_import_boundaries.py
python -m pytest -q        # 31 passed, 1 skipped (API tests skip until: pip install fastapi httpx)
```

## Rules that CI enforces

- `research/reasoning` and `research/baselines` never import `contracts.truth`, `research.ground_truth`, `contracts.interfaces`,
  `contracts.mocks` or `ingestion`.
- `research/ground_truth` never imports `ingestion`, `sqlglot`, `research.reasoning` or `research.baselines`.
- `research/` never imports `backend` or `frontend`.
- The engine and every baseline raise `LeakageError` if a ground-truth object, label or `ground_truth` coverage mode reaches them.

## Deviations from the pack's Section 16 sketch

1. Ground-truth-only types moved to `contracts/truth.py` so the import rule can be enforced by module name.
2. `PredictorInput` has no separate coverage list: coverage rides on each `RuntimeEvidence`.
3. `RuntimeEvidence` refuses to be built as a negative evaluation unless its coverage is complete, runtime-mode and covers the key.

## Known limits of this first slice

- R0 (temporal filtering) is the repository's job. The engine only carries the temporal context.
- `PARTIAL` static semantics never allow REFUTED_FOR_RUN. Per the contract algorithm, R1 (unsupported static) comes before
  positive runtime evidence, so unsupported static semantics yield UNKNOWN even when a positive event exists. Review this
  with the team.
- How coverage is derived (D-09), what counts as positive runtime evidence (D-10), ground-truth semantics (D-11) and the
  prediction-unit universe (D-12) are open decisions in the pack. The metrics score only units present in both predictions
  and truth, and report the rest as `unscored_predictions` and `unpredicted_truth`.

## Your first day

Each directory has a README naming its owner and first tasks. The per-member plans are Sections 30 to 34 of the pack.
Work on your own `feature/...` branch, open pull requests, never push to `main`.
