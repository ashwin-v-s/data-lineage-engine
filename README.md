# Kairos: data lineage & metadata engine (research prototype)

Bitemporal lineage infrastructure plus a provisional research layer: coverage-aware, execution-conditioned reasoning over static lineage and incomplete runtime evidence. The full design is in [docs/FINAL_ARCHITECTURE_AND_RESEARCH_EXECUTION_PACK.md](docs/FINAL_ARCHITECTURE_AND_RESEARCH_EXECUTION_PACK.md). Read it first.

## What exists today

| Area | Status |
|---|---|
| `backend/app/main.py` FastAPI health + mock dependency slice | IMPLEMENTED (PLUMBING); mock dependency result is not a production catalog |
| `backend/app/services/metadata_normalizer.py` | IMPLEMENTED as a side-effect-free JSON metadata preview normalizer |
| `POST /api/v1/metadata/preview` | ADDED on this feature branch; generic JSON records, explicit relationships only, not persisted |
| `docs/COMPETITOR_ARCHITECTURE_RESEARCH.md` | Added official-source research notes for DataHub, OpenMetadata, OpenLineage/Marquez, Open Data Hub, and OpenMeter scope clarification |
| `docs/adr/ADR-001-universal-metadata-preview.md` | Proposed decision record; team review required |
| `contracts/` shared types, Protocols, mocks, fixtures | IMPLEMENTED (PROVISIONAL, freeze at architecture freeze) |
| Reasoning engine, rules R1 to R5 (`research/reasoning`) | IMPLEMENTED on mocks, NOT VALIDATED |
| Baselines B1 to B5 (`research/baselines`) | IMPLEMENTED on mocks, NOT VALIDATED |
| Metrics (`research/metrics`) | IMPLEMENTED, unit-tested against hand-computed counts |
| Leakage guards and import-boundary checker | IMPLEMENTED |
| Database persistence, temporal queries, authenticated live connectors, scheduled scans, UI integration | NOT IMPLEMENTED by this change |
| Any experiment result | NOT YET MEASURED. Illustrative fixtures are not experimental data. |

**New here? Read `docs/TEAM_GUIDE.md` and the architecture/research pack.** They remain the source of team workflow and scope constraints.

## Generic metadata preview

Once the FastAPI dependencies are installed and the app is running, send JSON to `POST /api/v1/metadata/preview`. The endpoint accepts a JSON object, an array of objects, or a common object property containing records. It preserves safe unknown fields, reports discovered fields and capability hints, and passes through a top-level `relationships` array only when the source explicitly supplies it.

Example:

```bash
curl -X POST 'http://127.0.0.1:8000/api/v1/metadata/preview?source_name=photo_archive' \
  -H 'Content-Type: application/json' \
  -d '[{"id":"img-1","path":"images/a.jpg","mime_type":"image/jpeg","width":1200}]'
```

**Important boundary:** this is an in-memory preview, not persistence, a live connector, or proof that arbitrary systems can already be connected. It does not infer relationships. Obvious credential-like field names are filtered as a defense-in-depth measure.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate      # Python 3.11+
pip install pytest fastapi httpx
python scripts/check_import_boundaries.py
python -m pytest -q
```

## Rules that CI enforces

- `research/reasoning` and `research/baselines` never import `contracts.truth`, `research.ground_truth`, `contracts.interfaces`, `contracts.mocks` or `ingestion`.
- `research/ground_truth` never imports `ingestion`, `sqlglot`, `research.reasoning` or `research.baselines`.
- `research/` never imports `backend` or `frontend`.
- The engine and every baseline raise `LeakageError` if a ground-truth object, label or `ground_truth` coverage mode reaches them.

## Known limits and open decisions

- R0 (temporal filtering) is the repository's job. The engine only carries the temporal context.
- `PARTIAL` static semantics never allow REFUTED_FOR_RUN. Per the contract algorithm, R1 (unsupported static) comes before positive runtime evidence, so unsupported static semantics yield UNKNOWN even when a positive event exists. Review this with the team.
- Coverage derivation (D-09), positive runtime evidence (D-10), ground-truth semantics (D-11), and prediction-unit universe (D-12) remain open decisions in the pack.
- Expanding MVP source scope or adding live connectors requires a team decision; see the competitor research and ADR-001.

## Workflow

Each directory has a README naming its owner and first tasks. The per-member plans are Sections 30 to 34 of the pack. Work on your own `feature/...` branch, open pull requests, and never push directly to `main`.
