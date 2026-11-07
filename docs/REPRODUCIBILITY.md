# Kairos M5 Reproducibility Guide

## System Overview
Kairos M5 provides the FastAPI REST representation, Pydantic schemas, and Stage 1 Investigator Cockpit for exploring historical lineage, bitemporal intervals, and four-state execution-conditioned reasoning.

## Prerequisites
- **Python**: 3.11+
- **Node.js**: v20+ (tested on v22.20.0 with npm 11.6.2)
- **Virtual Environment**: Activated virtualenv or system python with dependencies installed.

## 1. Backend Setup & Test Execution

### Install Python Dependencies
```bash
# From repository root
pip install pytest fastapi uvicorn httpx pydantic
```

### Check Architectural Import Boundaries
```bash
python scripts/check_import_boundaries.py
# Expect: "import boundaries: ok"
```

### Run API & Contract Test Suite
```bash
python -m pytest tests/test_api_v1.py -v
```

### Run Verification & Demo Script
```bash
python scripts/demo_m5.py
```

## 2. Frontend Setup & Build

### Development Mode (with Vite Hot-Module Reloading)
```bash
cd frontend
npm install
npm run dev
# Vite runs at http://localhost:3000 and proxies /api/v1 to http://127.0.0.1:8000
```

### Production Build
```bash
cd frontend
npm run build
# Compiles to frontend/dist/
```

## 3. Running Integrated System (FastAPI + React Cockpit)

```bash
# Starts backend and automatically serves the compiled frontend at http://127.0.0.1:8000/
python scripts/run_ui.py --port 8000 --open-browser
```

Interactive Endpoints:
- **Investigator Cockpit**: `http://127.0.0.1:8000/`
- **Interactive Swagger Docs**: `http://127.0.0.1:8000/docs`
- **Alternative ReDoc**: `http://127.0.0.1:8000/redoc`

## 4. Contract Verification Matrix

> **As-of commit:** `feature/reasoning-experiments` post-merge with main (`d5d7b15`)
> **Measured:** 2026-11-02 — routes verified against the running application.
> Routes marked ⚠️ existed in an earlier branch and have been superseded or removed.

| Route | Method | Purpose | Verified In | Notes |
|---|---|---|---|---|
| `/healthz` | GET | Public unauthenticated liveness probe | `scripts/demo_m5.py` check 1 | Returns 200 without auth |
| `/api/v1/auth/config` | GET | Public auth configuration (Supabase URL + anon key) | `scripts/demo_m5.py` check 1 | Returns 200 without auth |
| `/api/v1/health` | GET | Authenticated health + DB check | `tests/test_api_v1.py` | Auth-gated since M1 hardening |
| `/api/v1/search` | GET | Text search for datasets & columns | `tests/test_api_v1.py::test_search_*` | Auth-gated |
| `/api/v1/catalog` | GET | Workspace-scoped asset catalog | `tests/test_live_api.py::test_catalog_read_returns_200` | Auth-gated; live-tested |
| `/api/v1/assets/{asset_id}` | GET | Asset detail by UUID or name | `scripts/demo_m5.py` check 4 | Auth-gated |
| `/api/v1/assets/{asset_id}/lineage` | GET | Bitemporal lineage graph | `scripts/demo_m5.py` check 5 | Auth-gated |
| `/api/v1/assets/{asset_id}/capabilities` | GET | Capability registry for asset | `tests/test_capabilities.py` | Auth-gated |
| `/api/v1/assets/{asset_id}/downstream-impact` | GET | Downstream impact analysis | `tests/test_live_api.py::test_downstream_impact_*` | Auth-gated |
| `/api/v1/runs/{run_id}/dependency/{source}/{target}` | GET | Four-state reasoning engine prediction | `scripts/demo_m5.py` check 6 | Auth-gated since M1 hardening |
| `/api/v1/ingest/preview` | POST | Validate + preview import (no DB write) | `tests/test_ingestion_api.py` | Auth-gated |
| `/api/v1/ingest/commit` | POST | Idempotent import commit | `tests/test_live_ingestion_storage.py` | Auth-gated; live-tested |
| `/api/v1/ingest/runs` | GET | Import run history | `tests/test_ingest_runs.py::test_list_runs_live_*` | Auth-gated; live-tested |
| `/api/v1/governance/slas` | GET/POST | Freshness SLA management | `scripts/demo_m5.py` check 8 | Auth-gated |
| `/api/v1/governance/incidents` | GET | Incident list | `tests/test_incidents.py` | Auth-gated |
| `/api/v1/governance/datasets/{id}/evaluate` | POST | Evaluate freshness for asset | `tests/test_freshness.py` | Auth-gated |
| `/api/v1/sources` | GET/POST | Source connection management | `tests/test_sources_api.py` | Auth-gated |
| `/api/v1/members` | GET | Workspace membership | `tests/test_membership_api.py` | Auth-gated |

**Routes from earlier branches that no longer exist (retired):**

| ⚠️ Old route | Replaced by | Ref |
|---|---|---|
| `/api/v1/entities/{entity_id}` | `/api/v1/assets/{asset_id}` | PR #12 |
| `/api/v1/entities/by-name` | `/api/v1/search` | PR #12 |
| `/api/v1/lineage/{entity_id}/graph` | `/api/v1/assets/{asset_id}/lineage` | PR #12 |
| `/api/v1/lineage/{entity_id}/upstream` | `/api/v1/lineage/{asset_id}/upstream` | PR #12 |
| `/api/v1/evidence/{evidence_id}` | `/api/v1/evidence-at-time` | PR #12 |
| `/api/v1/evaluation/oracle/{run_id}` | Removed — research-only, not a product route | PR #11 |

The test functions `test_entity_endpoints`, `test_lineage_graph_and_truncation_headers`,
`test_evidence_endpoints`, `test_evaluation_oracle_isolated_mode` referenced above
no longer exist in `tests/test_api_v1.py`. See current test file for active tests.

## 5. Research Benchmark Matrix (M4 — PLUMBING only)

> ⚠️ **PLUMBING EVIDENCE ONLY.** This runs the mock `w03_case_when` fixture through the
> plumbing pipeline. The numbers it produces are **NOT research findings**. See
> [`docs/BENCHMARK_RESULTS.md`](BENCHMARK_RESULTS.md) for the captured results, their
> interpretation, and the decisions that still block a real run.

### Prerequisites
```bash
# From repository root
python -m pip install -e ".[dev]"
```

### Run a single plumbing cell
```bash
python research/experiments/run.py --protocol research/protocol/v1.yaml --plumbing --loss-level 0 --seed 1
# Writes research/results/result_plumbing_mcar0_seed1.json
```

Valid loss levels: `0, 10, 30, 50, 70, 90` (the LOCKED matrix). Any integer seed is allowed.

### Run the full benchmark matrix end to end
```bash
python scripts/run_benchmark_matrix.py
```
This invokes the real runner once per cell across the full loss-level matrix
(`0, 10, 30, 50, 70, 90`) × seeds (`1, 7, 42`) = 18 cells, then consolidates every artifact
into two committed deliverables under `research/results/`:

- `research/results/summary.json` — machine-readable per-(level, seed, method) metrics plus
  each artifact's `mask_hash` / `ground_truth_hash` / `git_sha`.
- `research/results/summary.md` — human-readable report, one table per loss level.

The individual `research/results/result_*.json` artifacts stay git-ignored; the two summary
files are intentionally tracked.

### Verify the plumbing pipeline against the protocol gates
```bash
python -m pytest tests/test_protocol_runner.py -q
python scripts/check_import_boundaries.py
```

### Full test suite
```bash
python -m pytest -q
```

The captured matrix results and their interpretation live in
[`docs/BENCHMARK_RESULTS.md`](BENCHMARK_RESULTS.md).
