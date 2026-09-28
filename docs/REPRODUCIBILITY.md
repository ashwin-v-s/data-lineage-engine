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

| Route | Method | Purpose | Verified In |
|---|---|---|---|
| `/api/v1/health` | GET | Liveness and storage health | `tests/test_api_v1.py::test_health` |
| `/api/v1/entities/{entity_id}` | GET | M3 entity lookup by canonical UUID or name | `tests/test_api_v1.py::test_entity_endpoints` |
| `/api/v1/entities/by-name` | GET | M3 entity lookup by FQN | `tests/test_api_v1.py::test_entity_endpoints` |
| `/api/v1/search` | GET | Text search for datasets & columns | `tests/test_api_v1.py::test_entity_endpoints` |
| `/api/v1/lineage/{entity_id}/graph` | GET | Half-open bitemporal traversal with truncation headers | `tests/test_api_v1.py::test_lineage_graph_and_truncation_headers` |
| `/api/v1/lineage/{entity_id}/upstream` | GET | Directional upstream traversal | `tests/test_api_v1.py::test_lineage_upstream_downstream` |
| `/api/v1/lineage/{entity_id}/downstream` | GET | Directional downstream traversal | `tests/test_api_v1.py::test_lineage_upstream_downstream` |
| `/api/v1/evidence/{evidence_id}` | GET | M3 authoritative evidence dossier with raw_event payload hash | `tests/test_api_v1.py::test_evidence_endpoints` |
| `/api/v1/evidence/search` | GET | Search evidence by operator, system, type | `tests/test_api_v1.py::test_evidence_endpoints` |
| `/api/v1/evidence/entity/{entity_id}` | GET | List evidence associated with an entity | `tests/test_api_v1.py::test_evidence_endpoints` |
| `/api/v1/runs/{run_id}/dependency/{source}/{target}` | GET | M4 FourStateEngine prediction serialization with fixed text | `tests/test_api_v1.py::test_m4_reasoning_and_fixed_interpretations` |
| `/api/v1/evaluation/oracle/{run_id}` | GET | Hazard-mode benchmark ground truth oracle | `tests/test_api_v1.py::test_evaluation_oracle_isolated_mode` |
