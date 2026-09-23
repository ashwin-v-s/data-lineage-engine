# KAIROS — Complete Project Context for Claude

**Project**: Kairos: Data Lineage & Metadata Engine  
**Status**: Week 1 Complete, Week 2 In Progress  
**Team**: 5 members (M1-M5)  
**Demo Date**: Tomorrow  
**Implementation Timeline**: 2 weeks total (1 complete, 1 remaining)

---

## 1. Project Overview

**Kairos** is an open-source, self-hostable data lineage and metadata engine built as a university research project. It tracks data dependencies across SQL transformations, runtime events, and metadata changes using a bitemporal (valid-time + transaction-time) PostgreSQL storage model.

**Mission**: Answer "what was the data lineage at time X, according to what we knew at time Y?" with coverage-aware reasoning over incomplete runtime evidence.

**Users**: Data engineers, data governance teams, BI/analytics teams investigating data quality and dependencies.

**Final System**: A web application that ingests SQL, OpenLineage events, and dbt metadata, reasons about data dependencies under incomplete evidence, and answers point-in-time lineage queries.

---

## 2. Problem Statement

### Current State
- Data lineage tools show EITHER static SQL analysis (what *could* happen) OR runtime traces (what *did* happen).
- When runtime evidence is incomplete (events lost, unsupported SQL, infrastructure failures), existing tools cannot distinguish between:
  - "We saw nothing" (evidence missing)
  - "It did not happen" (no dependency in this run)
  
This leads to false conclusions about which data actually contributed to a specific output.

### Solution Approach
**Kairos** combines:
- **Static analysis** (SQLGlot): What *could* a query depend on?
- **Runtime observation** (OpenLineage): What *did* we actually see?
- **Coverage awareness** (ProvSQL/reference interpreter): What *should* we have seen if the dependency occurred?
- **Four-state reasoning**: OBSERVED, REFUTED_FOR_RUN, POSSIBLE, UNKNOWN

---

## 3. Final Intended System (MVP)

```
SQL Query + dbt Manifest + OpenLineage Events
    ↓
[Ingestion Layer] → SQLGlot, OpenLineage normalization
    ↓
[PostgreSQL] → Bitemporal storage (valid_time + transaction_time)
    ↓
[Reasoning Engine] → Four-state classification (R1-R5 rules)
    ↓
[REST API] → /api/v1/lineage, /api/v1/lineage/as_of
    ↓
[UI] → Lineage explorer with time controls (valid_at, known_as_of)
    ↓
User: "Show me lineage as of Sept 20, 2026, based on what we knew Sept 15"
```

### MVP Completion Ladder
1. **MVP-0**: Research core (fixtures, ground truth, baselines, metrics) ✅ COMPLETE
2. **MVP-1**: PostgreSQL bitemporal storage ✅ COMPLETE
3. **MVP-2**: SQLGlot + OpenLineage + dbt ingestion ⏳ M2/partial
4. **MVP-3**: REST API ⏳ M5/partial
5. **MVP-4**: UI Stage 1 (explorer, time controls) ❌ NOT STARTED
6. **MVP-5**: Integrated demo ⏳ IN PROGRESS

---

## 4. Architecture

### 4.1 High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│            EVIDENCE / METADATA LAYER  (M1, M2)                  │
│   Raw SQL / Events / Manifest  →  Normalized Evidence           │
└─────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│              POSTGRESQL  =  AUTHORITY  (M3)                      │
│   Identity, temporal versions, evidence, derived states         │
└─────────────────────────────────────────────────────────────────┘
            ↓                                    ↓
    ┌──────────────────┐          ┌──────────────────────────┐
    │ Bitemporal       │          │ Neo4j Projection         │
    │ Lineage Queries  │          │ (optional, measured need)│
    │ (M3)             │          └──────────────────────────┘
    └──────────────────┘
            ↓
┌─────────────────────────────────────────────────────────────────┐
│        EXECUTION-CONDITIONED REASONING  (M4)                     │
│   OBSERVED / REFUTED_FOR_RUN / POSSIBLE / UNKNOWN               │
└─────────────────────────────────────────────────────────────────┘
            ↓
    ┌───────────────────────────────────────┐
    │  FastAPI /api/v1  (M5)                │
    │  UI / Dashboard   (M5)                │
    └───────────────────────────────────────┘
```

### 4.2 Component Breakdown

| Component | Owner | Status | Purpose |
|-----------|-------|--------|---------|
| **Contracts** | M4 | ✅ COMPLETE | Shared types, interfaces, validation |
| **M1: SQLGlot Adapter** | M1 | ✅ COMPLETE | SQL parsing, static lineage extraction |
| **M1: dbt Manifest** | M1 | ✅ COMPLETE (adapter) | Parse dbt manifests for metadata |
| **M1: B1 Baseline** | M1 | ✅ COMPLETE | Static-only baseline |
| **M2: OpenLineage** | M2 | ⏳ FRAMEWORK | Runtime event ingestion |
| **M2: Ground Truth** | M2 | ❌ SPIKE PENDING | ProvSQL or reference interpreter |
| **M3: PostgreSQL Schema** | M3 | ✅ COMPLETE | Bitemporal storage (0001_core.sql) |
| **M3: Temporal Queries** | M3 | ✅ COMPLETE | Oracle functions, as_of logic |
| **M3: Identity** | M3 | ✅ COMPLETE | Canonical IDs for datasets/columns |
| **M4: Four-State Engine** | M4 | ✅ COMPLETE | Rules R1-R5 reasoning |
| **M4: Baselines B2-B5** | M4 | ✅ COMPLETE | Alternative prediction strategies |
| **M4: Metrics** | M4 | ✅ COMPLETE | Evaluation framework |
| **M4: Loss Simulator** | M4 | ✅ COMPLETE (MOCK) | Simulate missing runtime evidence |
| **M5: FastAPI** | M5 | ⏳ PARTIAL | REST API endpoints |
| **M5: UI** | M5 | ❌ NOT STARTED | Frontend (Stage 1 planned) |

---

## 5. Repository Structure

```
data-lineage-engine/
│
├── README.md                              Project overview, quick start
├── pyproject.toml                         Dependencies, Python config
├── .env.example                           Environment template
│
├── docs/
│   ├── FINAL_ARCHITECTURE_AND_RESEARCH_EXECUTION_PACK.md    (164 KB, comprehensive)
│   ├── TEAM_GUIDE.md                      Week 1 setup and member guides
│   ├── DATA_MODEL.md                      PostgreSQL schema docs (M3)
│   ├── POSTGRESQL_SETUP.md                Database setup guide (M3)
│   └── M3_WEEK1_CHECKPOINT_REPORT.md      M3 completion status
│
├── contracts/                              ⭐ SHARED INTERFACES (M4 owned)
│   ├── types.py                           (210 lines) Enums, dataclasses
│   ├── evidence.py                        (445 lines) StaticEvidence, RuntimeEvidence, Prediction
│   ├── truth.py                           (85 lines) GroundTruthRecord (import-protected)
│   ├── interfaces.py                      (212 lines) Abstract interfaces for all modules
│   ├── mocks/
│   │   ├── loaders.py                     JSON fixture loading
│   │   ├── providers.py                   Mock static/runtime/truth providers
│   │   └── __init__.py
│   ├── fixtures/
│   │   ├── w03_case_when.json             ✅ Test case (SQL: CASE WHEN)
│   │   └── w03_case_when.truth.json       Mock ground truth
│   └── __init__.py
│
├── ingestion/                              M1/M2 owned
│   ├── sql/                               ⭐ M1 COMPLETE
│   │   ├── parser.py                      SQLGlot integration (490 lines)
│   │   ├── adapter.py                     StaticLineageProvider implementation
│   │   ├── SUPPORT_MATRIX.md              ✅ Documented SQL support
│   │   ├── corpus/                        ✅ 12 test cases
│   │   │   ├── w01_simple_select.json
│   │   │   ├── w02_join.json
│   │   │   ├── w03_case_when.json
│   │   │   └── ... (more test cases)
│   │   ├── b1_adapter.py                  ✅ B1 baseline wrapper
│   │   └── __init__.py
│   ├── openlineage/                       ⏳ M2 FRAMEWORK
│   │   ├── README.md                      Member 2 notes
│   │   └── __init__.py
│   ├── dbt/                               ⏳ M2 FRAMEWORK
│   │   ├── README.md                      dbt adapter notes
│   │   └── __init__.py
│   └── __init__.py
│
├── backend/                                M3/M5 owned
│   ├── app/
│   │   ├── main.py                        ⏳ FastAPI app (MINIMAL, health check only)
│   │   ├── temporal/
│   │   │   ├── reference.py               ✅ Temporal oracle (89 lines)
│   │   │   └── __init__.py
│   │   ├── identity/
│   │   │   ├── canonical_ids.py           ✅ Identity canonicalization (257 lines)
│   │   │   └── __init__.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── (NO ROUTES IMPLEMENTED YET)
│   │   ├── repositories/
│   │   │   └── __init__.py                (Placeholder)
│   │   ├── services/
│   │   │   └── __init__.py                (Placeholder)
│   │   └── __init__.py
│   ├── migrations/
│   │   ├── 0001_core.sql                  ✅ M3 COMPLETE (232 lines)
│   │   │   - dataset table
│   │   │   - raw_event table
│   │   │   - edge_temporal_version table
│   │   │   - temporal queries
│   │   ├── README.md                      Migration guide
│   │   └── __init__.py
│   ├── README.md                          Backend overview
│   └── __init__.py
│
├── research/                               M2/M4 owned
│   ├── reasoning/
│   │   ├── engine.py                      ✅ FourStateEngine (360 lines)
│   │   │   - Rule R1: UNKNOWN if unsupported
│   │   │   - Rule R2: OBSERVED if positive evidence
│   │   │   - Rule R3: REFUTED_FOR_RUN if complete negative eval
│   │   │   - Rule R4: POSSIBLE if static but no evidence
│   │   │   - Rule R5: UNKNOWN if nothing
│   │   └── __init__.py
│   ├── baselines/
│   │   ├── baselines.py                   ✅ COMPLETE (380 lines)
│   │   │   - B1: StaticOnly (M1 provides input)
│   │   │   - B2: NegativeAssumption (runtime-only, refutes on missing)
│   │   │   - B3: Union (naive combination)
│   │   │   - B4: ThreeState (no REFUTED_FOR_RUN)
│   │   │   - B5: CoverageGated (requires complete evaluation)
│   │   └── __init__.py
│   ├── metrics/
│   │   ├── metrics.py                     ✅ COMPLETE (280 lines)
│   │   │   - Confusion matrix (TP, TN, FP, FN)
│   │   │   - Committed accuracy, false refutation, etc.
│   │   │   - Handles NA for zero denominators
│   │   └── __init__.py
│   ├── ground_truth/                      ⏳ M2 owns (NOT STARTED)
│   │   ├── README.md                      ProvSQL spike, reference interpreter
│   │   └── __init__.py
│   ├── protocol/                          ⏳ M4 defines (FRAMEWORK)
│   │   ├── v1.yaml                        Protocol definition (placeholder)
│   │   └── __init__.py
│   ├── experiments/                       ⏳ FRAMEWORK
│   │   ├── run.py                         Experiment runner (placeholder)
│   │   └── __init__.py
│   ├── missingness/                       ⏳ FRAMEWORK (loss simulation)
│   │   ├── mcar.py                        Missing-completely-at-random
│   │   └── __init__.py
│   ├── benchmarks/                        ⏳ EMPTY (M4)
│   ├── results/                           ⏳ EMPTY (M4)
│   └── __init__.py
│
├── tests/                                  ✅ 63 PASSING TESTS
│   ├── test_engine_rules.py               ✅ (20 tests) M4: R1-R5 rules
│   ├── test_baselines.py                  ✅ (5 tests) M4: B1-B5 correctness
│   ├── test_metrics.py                    ✅ (3 tests) M4: metric calculations
│   ├── test_leakage.py                    ✅ (4 tests) Ground truth isolation
│   ├── test_fixtures_plumbing.py          ✅ (4 tests) Mock data validation
│   ├── test_static_corpus.py              ✅ M1: (12 tests) SQL parsing correctness
│   ├── test_static_alias_resolution.py    ✅ M1: (6 tests) Table alias handling
│   ├── test_static_fingerprints.py        ✅ M1: (4 tests) Query fingerprinting
│   ├── test_static_unsupported.py         ✅ M1: (5 tests) Unsupported SQL detection
│   ├── test_api_slice.py                  ⏳ (3 tests) API endpoints (skipped: needs fastapi)
│   ├── test_identity.py                   ✅ M3: (18 tests) Canonical ID handling
│   ├── test_temporal_oracle.py            ✅ M3: (13 tests) Point-in-time queries
│   └── (more test files)                  ✅ TOTAL: 63 PASSED, 2 SKIPPED
│
├── scripts/
│   ├── check_import_boundaries.py         ✅ CI enforcement
│   └── make_fixtures.py                   Fixture regeneration
│
├── configs/                                ⏳ M3/M5 placeholder
│   └── README.md
│
├── data/                                   Git-ignored (for raw data)
│   └── .gitkeep
│
├── frontend/                               ❌ M5 (NOT STARTED)
│   └── README.md
│
└── .github/
    ├── CODEOWNERS                         Code review ownership
    └── workflows/ci.yml                   ✅ CI pipeline (import check, pytest)
```

---

## 6. Original Two-Week Plan

### WEEK 1 (Completed)

#### M1: Static Metadata Ingestion & SQL Lineage
**Planned**: SQLGlot adapter, corpus, support matrix, B1 baseline, tests  
**Actual**: ✅ **COMPLETE**
- 490 lines: parser.py (SQLGlot integration)
- 12 corpus test cases with expected dependencies
- Support matrix (SUPPORTED, PARTIAL, UNSUPPORTED)
- B1 baseline adapter
- 12 dedicated tests + 31 total M1 tests
- All passing

#### M2: Runtime Evidence & Ground Truth
**Planned**: ProvSQL spike, OpenLineage ETL, runtime evidence normalization  
**Actual**: ⏳ **SPIKE PENDING**
- Framework structure created
- No ProvSQL investigation yet
- No OpenLineage implementation
- Ground truth provider interface defined but not implemented

#### M3: Storage & Bitemporal Lineage
**Planned**: PostgreSQL schema, temporal oracle, identity resolution  
**Actual**: ✅ **COMPLETE**
- 232 lines: 0001_core.sql (dataset, raw_event, edge_temporal_version tables)
- 89 lines: reference.py (temporal oracle with `visible()` function)
- 257 lines: canonical_ids.py (ID canonicalization logic)
- 18 + 13 = 31 tests for identity and temporal queries
- All passing

#### M4: Reasoning Engine & Metrics
**Planned**: Four-state engine (R1-R5), baselines (B1-B5), metrics, loss simulator  
**Actual**: ✅ **COMPLETE**
- 360 lines: engine.py (FourStateEngine with R1-R5 rules)
- 380 lines: baselines.py (B1-B5 reasoning strategies)
- 280 lines: metrics.py (confusion matrix, commitment rates, etc.)
- 32 dedicated tests (all passing)
- Ground truth leakage protection enforced

#### M5: Backend API & Frontend
**Planned**: FastAPI /api/v1 endpoints, Stage 1 UI  
**Actual**: ⏳ **MINIMAL (HEALTH CHECK ONLY)**
- `main.py` exists with `/health` endpoint only
- No lineage query endpoints
- No UI implemented
- Framework in place

### WEEK 2 (Planned Remaining Work)

#### M1
- **Status**: ✅ COMPLETE (continue testing on real data in M2 ETL)
- **Note**: No additional work, support M2/M5 integration

#### M2: Runtime Evidence & Ground Truth
- **Planned**: Complete ProvSQL spike, implement OpenLineage ETL, runtime evidence provider
- **Expected**: 40+ hours
- **Output**: Spike report, working ETL, ground truth provider

#### M3: Storage & Temporal
- **Status**: ✅ COMPLETE
- **Note**: Support M2 integration and M5 API queries

#### M4: Reasoning Engine & Metrics
- **Status**: ✅ COMPLETE
- **Note**: Support M5 API integration

#### M5: Backend API & Frontend
- **Planned**: REST API endpoints, basic UI
- **Expected**: 60-80 hours (API 40 hrs, UI 20-40 hrs)
- **Output**: /api/v1 endpoints, Stage 1 UI with time controls

---

## 7. Week 1 — Planned vs Actual (Detailed)

### Completion Matrix

| Component | Planned | Actual | Status | Evidence |
|-----------|---------|--------|--------|----------|
| **M1: SQLGlot Parser** | Full | Full | ✅ COMPLETE | `ingestion/sql/parser.py` (490 lines) |
| **M1: SQL Corpus** | 12 cases | 12 cases | ✅ COMPLETE | `ingestion/sql/corpus/*.json` |
| **M1: Support Matrix** | Doc | Doc | ✅ COMPLETE | `ingestion/sql/SUPPORT_MATRIX.md` |
| **M1: B1 Adapter** | Wrapper | Wrapper | ✅ COMPLETE | `ingestion/sql/b1_adapter.py` |
| **M1: Tests** | Multiple | 12 specific | ✅ COMPLETE | `tests/test_static_*.py` (31 M1 tests) |
| **M2: ProvSQL Spike** | Investigation | NOT DONE | ⏳ PENDING | No spike report |
| **M2: OpenLineage ETL** | Full | NOT DONE | ❌ MISSING | Framework only |
| **M2: Runtime Provider** | Full | NOT DONE | ❌ MISSING | Interface defined, no impl |
| **M3: PostgreSQL Schema** | Full | Full | ✅ COMPLETE | `backend/migrations/0001_core.sql` (232 lines) |
| **M3: Temporal Oracle** | Full | Full | ✅ COMPLETE | `backend/app/temporal/reference.py` (89 lines) |
| **M3: Identity** | Full | Full | ✅ COMPLETE | `backend/app/identity/canonical_ids.py` (257 lines) |
| **M3: Tests** | Multiple | Multiple | ✅ COMPLETE | `tests/test_temporal_oracle.py` (13), `test_identity.py` (18) |
| **M4: Engine** | Full | Full | ✅ COMPLETE | `research/reasoning/engine.py` (360 lines) |
| **M4: Baselines** | B1-B5 | B1-B5 | ✅ COMPLETE | `research/baselines/baselines.py` (380 lines) |
| **M4: Metrics** | Full | Full | ✅ COMPLETE | `research/metrics/metrics.py` (280 lines) |
| **M4: Tests** | Multiple | Multiple | ✅ COMPLETE | `tests/test_engine_rules.py` (20), `test_baselines.py` (5), etc. |
| **M5: API Endpoints** | Multiple | Health check | ❌ MINIMAL | `backend/app/main.py` only |
| **M5: UI** | Stage 1 | NOT DONE | ❌ NOT STARTED | No frontend code |

### Key Metrics

- **Total Tests**: 65 (63 passing, 2 skipped waiting for fastapi)
- **Lines of Implementation**: ~3,500 (M1:600, M3:500, M4:1020, contracts:800, tests:600+)
- **Completion**: 60% (M1 ✅, M3 ✅, M4 ✅, M2 framework ⏳, M5 minimal ❌)

---

## 8. Current Working System

### What Can Be Demonstrated NOW

#### 8.1 M1: SQL Lineage Extraction

**Status**: ✅ **FULLY WORKING**

**Input**: SQL query + schema

```sql
SELECT CASE WHEN country = 'US' THEN salary ELSE 0 END AS adjusted_salary
FROM employees
```

**Processing**:
1. SQLGlot parses query
2. Extracts dependencies: `employees.country`, `employees.salary` → `adjusted_salary`
3. Validates against corpus expected values
4. Generates StaticEvidence objects

**Output**: StaticEvidence list with column-level dependencies

**Demo Command**:
```bash
python -m pytest tests/test_static_corpus.py -v
```

**Result**: ✅ All 12 corpus tests pass

---

#### 8.2 M3: Bitemporal Storage & Temporal Queries

**Status**: ✅ **SCHEMA COMPLETE, QUERIES WORK**

**PostgreSQL Schema**:
```sql
-- Created by 0001_core.sql
CREATE TABLE dataset (id UUID PRIMARY KEY, ...);
CREATE TABLE raw_event (event_id TEXT PRIMARY KEY, ...);
CREATE TABLE edge_temporal_version (
    version_id UUID PRIMARY KEY,
    edge_id UUID NOT NULL,
    valid_from TIMESTAMPTZ,      -- When this edge was valid in reality
    valid_to TIMESTAMPTZ,         -- When this edge ended
    transaction_from TIMESTAMPTZ, -- When we learned this
    transaction_to TIMESTAMPTZ    -- When we updated our belief
);
```

**Temporal Query Example** (Python):
```python
from backend.app.temporal.reference import visible

versions = [
    {"edge": "A->B", "valid_from": D(2026, 1, 1), "valid_to": None,
     "tx_from": D(2026, 1, 2), "tx_to": D(2026, 3, 10)},
    {"edge": "A->C", "valid_from": D(2026, 3, 1), "valid_to": None,
     "tx_from": D(2026, 3, 10), "tx_to": None},
]

# Query: "Show lineage valid on March 5, as we knew it on March 11"
result = visible(versions, D(2026, 3, 5), D(2026, 3, 11))
# Returns: ["A->C"] (correction was learned on March 10)
```

**Demo Command**:
```bash
python -m pytest tests/test_temporal_oracle.py -v
```

**Result**: ✅ All 13 temporal tests pass

---

#### 8.3 M4: Reasoning Engine

**Status**: ✅ **FULLY WORKING (on mock data)**

**Input**: PredictorInput (static evidence + runtime evidence)

```python
from contracts.mocks.loaders import load_case, load_truth
from contracts.evidence import PredictorInput
from research.reasoning.engine import FourStateEngine

keys, static, runtime = load_case('w03_case_when')
truth = {r.key: r.label for r in load_truth('w03_case_when')}
inp = PredictorInput(tuple(keys), tuple(static), tuple(runtime))
```

**Processing**: FourStateEngine applies R1-R5 rules

```
R1: If unsupported static → UNKNOWN
R2: If positive runtime evidence → OBSERVED
R3: If static+supported + complete negative eval → REFUTED_FOR_RUN
R4: If static but no evidence → POSSIBLE
R5: If nothing → UNKNOWN
```

**Output**: Predictions with states (OBSERVED, REFUTED_FOR_RUN, POSSIBLE, UNKNOWN)

**Example Result**:
```
employees.country → adjusted_salary: OBSERVED (R2: positive evidence)
employees.salary → adjusted_salary: OBSERVED (R2: positive evidence)
```

**Demo Command**:
```bash
python test_demo.py  # Full end-to-end demo
```

**Output**:
```
============================================================
DATA LINEAGE ENGINE - END-TO-END DEMO
============================================================
1. ✅ STATIC EVIDENCE LOADED (M1 - SQL Parsing)
   - Found 2 static dependencies
2. ✅ RUNTIME EVIDENCE LOADED (M2 - OpenLineage)
   - Found 4 runtime observations
3. ✅ DATABASE SCHEMA READY (M3 - Storage)
4. ✅ REASONING ENGINE RUNNING (M4 - Four-State)
   - Generated 8 predictions
5. ✅ METRICS CALCULATED
   - Accuracy: 100.0%
   - False Refutations: 0.0
6. 📊 BASELINE COMPARISON
   - B2 Baseline Accuracy: 62.5%
============================================================
✅ FULL PIPELINE WORKING END-TO-END!
============================================================
```

---

#### 8.4 M5: FastAPI Endpoints

**Status**: ⏳ **MINIMAL**

**Currently Implemented**:
```python
# backend/app/main.py
@app.get("/health")
def health_check():
    return {"status": "ok"}
```

**NOT Yet Implemented**:
- `/api/v1/lineage/{entity_id}`
- `/api/v1/lineage/as_of`
- Request validation
- Response formatting
- Database queries
- Error handling

---

### End-to-End Flow (What Currently Works)

```
User (or test)
    ↓
Load mock SQL + schema + runtime events (fixtures)
    ↓
M1: SQLGlot parses SQL → StaticEvidence
    ↓
M2: Mock providers provide RuntimeEvidence (no real OpenLineage yet)
    ↓
M4: FourStateEngine reasons over evidence
    ↓
M4: Metrics evaluates predictions vs ground truth
    ↓
Output: Predictions, metrics, state distributions
```

**Demo File**: `test_demo.py` (fully functional)

---

## 9. Current UI

### Status: ❌ **NOT STARTED**

**Planned (Stage 1)**:
- Simple explorer interface
- Two time controls: `valid_at` and `known_as_of`
- Lineage display (upstream/downstream)
- Evidence panel
- Entity search

**Current**: No UI code exists yet.

**Technology Stack (Planned)**:
- React or Vue (not yet chosen)
- D3.js or vis.js for graph visualization
- TBD

---

## 10. Current APIs

### REST API Status: ⏳ **MINIMAL**

**Currently Implemented**:
```
GET /health → {"status": "ok"}
```

**Planned (Week 2)**:
```
GET  /api/v1/lineage/{entity_id}
GET  /api/v1/lineage/as_of?valid_at=...&known_as_of=...
POST /api/v1/lineage/query (with filters)
GET  /api/v1/datasets
GET  /api/v1/datasets/{id}/lineage
```

**Request Format (TBD)**:
```json
{
  "entity_id": "dataset.column",
  "valid_at": "2026-09-20T00:00:00Z",
  "known_as_of": "2026-09-20T12:00:00Z",
  "direction": "upstream" | "downstream" | "both"
}
```

**Response Format (TBD)**:
```json
{
  "entities": [...],
  "relationships": [...],
  "temporal_context": {...},
  "evidence": [...]
}
```

---

## 11. Current Database/Graph Structure

### 11.1 PostgreSQL Schema (M3)

**Tables** (from `backend/migrations/0001_core.sql`):

#### dataset
```sql
CREATE TABLE dataset (
  id UUID PRIMARY KEY,
  source_system TEXT NOT NULL,
  namespace TEXT NOT NULL,
  database_name TEXT NOT NULL,
  schema_name TEXT NOT NULL,
  name TEXT NOT NULL,
  asset_type TEXT NOT NULL,  -- 'table', 'view', 'column', etc.
  UNIQUE (source_system, namespace, database_name, schema_name, name, asset_type)
);
```

#### raw_event
```sql
CREATE TABLE raw_event (
  event_id TEXT PRIMARY KEY,  -- Unique event identifier
  payload JSONB NOT NULL,      -- Raw ingestion payload
  payload_hash TEXT NOT NULL,  -- SHA-256 of canonical payload
  ingestion_time TIMESTAMPTZ DEFAULT now()
);
```

#### edge_temporal_version
```sql
CREATE TABLE edge_temporal_version (
  version_id UUID PRIMARY KEY,
  edge_id UUID NOT NULL,
  valid_from TIMESTAMPTZ NOT NULL,    -- When edge started in reality
  valid_to TIMESTAMPTZ,                -- When edge ended (NULL = ongoing)
  transaction_from TIMESTAMPTZ NOT NULL, -- When we recorded this version
  transaction_to TIMESTAMPTZ,           -- When we superseded this version
  
  CHECK (valid_to IS NULL OR valid_from < valid_to),
  CHECK (transaction_to IS NULL OR transaction_from < transaction_to)
);
```

**Key Design Decisions**:
- `dataset` table uses 7-tuple identity (source_system, namespace, database_name, schema_name, name, asset_type)
- `edge_temporal_version` keeps all historical versions (never overwritten)
- Bitemporal: valid_time (reality) × transaction_time (knowledge)
- Immutable raw_event log

---

### 11.2 Data Model (M3)

**Identity Tuple**:
```python
class CanonicalID:
    source_system: str      # 'postgres', 'bigquery', 'snowflake', etc.
    namespace: str          # Database name or project
    schema_name: str        # Schema or dataset
    table_name: str         # Table name
    column_name: str        # Column (optional, None for table-level)
```

**Valid Time vs Transaction Time**:
```
Reality Timeline (valid_time):
  2026-01-01: customer_id added to orders
  2026-03-01: customer_id removed (business logic change)
  2026-09-20: (current)

Knowledge Timeline (transaction_time):
  2026-01-02: We recorded "customer_id added on 01-01"
  2026-03-10: We recorded "customer_id removed on 03-01"
  2026-09-20: (current)

Query: "What lineage was valid on March 5, based on what we knew March 11?"
Answer: Uses versions valid_from ≤ 2026-03-05 AND transaction_from ≤ 2026-03-11
```

---

### 11.3 Neo4j (Not Implemented)

**Current Status**: ❌ **NOT STARTED**

**Planned (after MVP-1 PostgreSQL measurements)**:
- Optional read-only projection
- Nodes: Dataset, Column, Transformation
- Relationships: CONTRIBUTES_TO, DERIVED_FROM, etc.
- Updated via outbox pattern

---

## 12. Static Lineage (M1)

### M1 Implementation Status: ✅ **COMPLETE**

### What M1 Does

**Input**: SQL query + schema

**Output**: StaticEvidence objects listing possible column dependencies

### SQL Support Matrix

| Construct | Status | Notes |
|-----------|--------|-------|
| SELECT * | ✅ SUPPORTED | Requires schema expansion |
| Column references | ✅ SUPPORTED | Tracked through aliases |
| JOIN (INNER) | ✅ SUPPORTED | Resolves aliases to table names |
| JOIN (LEFT/RIGHT/FULL) | ❌ UNSUPPORTED | Marked as UNSUPPORTED |
| WHERE clause | ✅ SUPPORTED | Adds to column dependencies |
| CASE WHEN | ✅ SUPPORTED | Includes condition + branches |
| COALESCE | ✅ SUPPORTED | All arguments included |
| Aggregate (SUM/AVG/MIN/MAX) | ✅ SUPPORTED | Over specific column |
| COUNT(*) | ⚠️ PARTIAL | Generates dataset-level evidence |
| GROUP BY | ✅ SUPPORTED | Group column tracked |
| CTE (WITH) | ✅ SUPPORTED | Recursive resolution |
| Subquery | ✅ SUPPORTED | Simple cases |
| Window Function | ❌ UNSUPPORTED | Marked as UNSUPPORTED |
| UDF | ❌ UNSUPPORTED | Marked as UNSUPPORTED |
| Dynamic SQL | ❌ UNSUPPORTED | Marked as UNSUPPORTED |
| Parse Error | ❌ UNSUPPORTED | Diagnostic provided |

### Key Files

| File | Lines | Purpose |
|------|-------|---------|
| `ingestion/sql/parser.py` | 490 | SQLGlot integration, fingerprinting |
| `ingestion/sql/adapter.py` | 200+ | StaticLineageProvider implementation |
| `ingestion/sql/b1_adapter.py` | 50 | B1 baseline wrapper |
| `ingestion/sql/SUPPORT_MATRIX.md` | - | Documentation of support |
| `ingestion/sql/corpus/` | 12 files | Test cases with expected dependencies |

### Test Coverage

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_static_corpus.py` | 12 | SQL construct validation |
| `test_static_alias_resolution.py` | 6 | Table/column alias handling |
| `test_static_fingerprints.py` | 4 | Query fingerprinting consistency |
| `test_static_unsupported.py` | 9 | Unsupported construct detection |
| **TOTAL** | **31** | ✅ All passing |

### Sample M1 Output

```python
StaticEvidence(
    evidence_id="static:abc123:employees.salary->adjusted_salary",
    source_column_id="employees.salary",
    target_column_id="adjusted_salary",
    granularity=Granularity.COLUMN,
    operator="case_branch",
    query_fingerprint="abc123...",
    parser_status=ParserStatus.SUPPORTED
)
```

---

## 13. Runtime Lineage (M2)

### M2 Implementation Status: ⏳ **FRAMEWORK ONLY**

### What M2 Should Do

**Input**: OpenLineage events (JSON)

**Output**: RuntimeEvidence objects listing observed column contributions

### Current State

**Framework Created**:
- `ingestion/openlineage/` directory
- `research/ground_truth/` directory (ProvSQL spike pending)
- Interface defined in `contracts/interfaces.py`

**NOT Implemented**:
- OpenLineage event parsing
- ProvSQL integration
- Ground truth provider
- Runtime evidence normalization

### Spike Status: PENDING

**Decision D-03**: ProvSQL license verification (PENDING)  
**Decision D-10**: What counts as positive runtime evidence (PENDING)  
**Decision D-11**: Ground-truth semantics (PENDING)

---

## 14. Evidence & Reasoning

### Evidence Types (Contracts)

#### StaticEvidence
```python
@dataclass
class StaticEvidence:
    evidence_id: str
    source_column_id: str
    target_column_id: str
    granularity: Granularity  # COLUMN, DATASET
    operator: str  # 'select', 'join', 'case_branch', etc.
    expression_fingerprint: str
    query_fingerprint: str
    schema_fingerprint: str
    parser_status: ParserStatus  # SUPPORTED, PARTIAL, UNSUPPORTED
```

#### RuntimeEvidence
```python
@dataclass
class RuntimeEvidence:
    evidence_id: str
    key: DependencyKey  # (run_id, source_col, target_col)
    covered_granularities: FrozenSet[Granularity]
    coverage_mode: CoverageMode  # PLUMBING, STRUCTURAL, GROUND_TRUTH
    is_mock: bool
    observation_time: Optional[datetime]
```

#### Prediction
```python
@dataclass
class Prediction:
    key: DependencyKey
    state: PredictedState  # OBSERVED, REFUTED_FOR_RUN, POSSIBLE, UNKNOWN
    evidence_ids: Tuple[str, ...]  # Traced back to source evidence
    version: str
    timestamp: datetime
```

### Four-State Reasoning (M4)

**Rules** (in order, first match wins):

| Rule | Condition | Result |
|------|-----------|--------|
| R1 | Unsupported static OR identity missing | UNKNOWN |
| R2 | Positive runtime evidence exists | OBSERVED |
| R3 | Static + fully supported + complete negative eval | REFUTED_FOR_RUN |
| R4 | Static + no evidence | POSSIBLE |
| R5 | Nothing points to dependency | UNKNOWN |

**Key Invariant**: Missing runtime evidence ≠ REFUTED_FOR_RUN

---

## 15. Point-in-Time / as_of

### Temporal Query Semantics

**Two Time Axes**:
1. **valid_time** (business time): When was this true in reality?
2. **transaction_time** (database time): When did we record this?

**Query**: "Show lineage valid on DATE, as known on DATE"

```python
result = visible(versions, valid_at=DATE1, known_as_of=DATE2)
```

**Implementation** (`backend/app/temporal/reference.py`):
```python
def visible(versions, valid_at, known_as_of):
    def inside(lo, hi, t):
        return lo <= t and (hi is None or t < hi)
    
    return sorted(v["edge"] for v in versions
                  if inside(v["valid_from"], v["valid_to"], valid_at)
                  and inside(v["tx_from"], v["tx_to"], known_as_of))
```

**Example**:
```
Edge: A→B, valid 2026-01-01 to 2026-03-01, recorded 2026-01-02 to 2026-03-10
Edge: A→C, valid 2026-03-01 onward, recorded 2026-03-10 onward

Query 1: valid_at=2026-03-05, known_as_of=2026-03-11
Result: [A→C] (updated edge after correction)

Query 2: valid_at=2026-03-05, known_as_of=2026-03-05
Result: [A→B] (old belief before correction)
```

---

## 16. Team Responsibilities

### Team Member Assignments

| Member | Role | Status | Main Files | Inputs | Outputs |
|--------|------|--------|-----------|--------|---------|
| **M1** | Static Metadata Ingestion & SQL Lineage | ✅ COMPLETE | `ingestion/sql/`, `tests/test_static_*` | SQL text, schema | StaticEvidence, B1 baseline |
| **M2** | Runtime Evidence & Ground Truth | ⏳ FRAMEWORK | `ingestion/openlineage/`, `research/ground_truth/` | OpenLineage events | RuntimeEvidence, GroundTruthProvider |
| **M3** | Storage & Bitemporal Lineage | ✅ COMPLETE | `backend/migrations/`, `backend/app/temporal/`, `backend/app/identity/` | Evidence records | PostgreSQL schema, temporal queries |
| **M4** | Reasoning Engine & Metrics | ✅ COMPLETE | `research/reasoning/`, `research/baselines/`, `research/metrics/`, `contracts/` | PredictorInput (evidence) | Predictions, metrics, evaluation |
| **M5** | Backend API & Frontend | ⏳ MINIMAL | `backend/app/main.py`, `frontend/` | Queries, UI interactions | REST API responses, UI renders |

### Ownership Matrix

```
contracts/              → M4 owned (custodian), all members review
ingestion/sql/          → M1 owned
ingestion/openlineage/  → M2 owned
ingestion/dbt/          → M2 owned (manifest parsing)
backend/migrations/     → M3 owned
backend/app/temporal/   → M3 owned
backend/app/identity/   → M3 owned
backend/app/api/        → M5 owns (not yet implemented)
research/reasoning/     → M4 owned
research/baselines/     → M4 owned
research/metrics/       → M4 owned
research/ground_truth/  → M2 owns (ProvSQL spike)
research/protocol/      → M4 owns (experiment definition)
research/experiments/   → M4 owns
frontend/               → M5 owns
tests/                  → Each member writes for their module + integration
```

### Inter-Member Dependencies

```
M1 (SQLGlot)
   ↓
M4 (Reasoning) ← M2 (OpenLineage) ← M3 (Storage)
   ↓                                  ↓
M5 (API/UI) ←────────────────────────┘
```

---

## 17. Week 2 — Remaining Implementation

### 17.1 M2: Runtime Evidence & Ground Truth

**Owner**: M2  
**Estimated Effort**: 40-50 hours  
**Status**: ⏳ NOT STARTED (framework exists)

#### Phase 1: ProvSQL Spike (Week 2 start)
- [ ] Install ProvSQL on local PostgreSQL
- [ ] Test cell-level provenance extraction
- [ ] Document feasibility and limitations
- [ ] Decision: Use ProvSQL vs ReferenceInterpreter

**Deliverable**: `research/ground_truth/SPIKE_REPORT.md`

#### Phase 2: OpenLineage ETL (Week 2 mid)
- [ ] Implement OpenLineageProvider
- [ ] Parse OpenLineage event stream
- [ ] Normalize to RuntimeEvidence
- [ ] Handle missing events correctly (never REFUTED_FOR_RUN)
- [ ] Write tests: duplicate events, late arrivals, out-of-order

**Deliverable**: `ingestion/openlineage/etl.py` + tests

#### Phase 3: Ground Truth Provider (Week 2 late)
- [ ] Implement GroundTruthProvider interface
- [ ] Query PostgreSQL + ProvSQL for truth labels
- [ ] Generate PROPAGATED / NOT_PROPAGATED labels
- [ ] Keep independent from predictor

**Deliverable**: `research/ground_truth/provider.py` + tests

### 17.2 M5: Backend API & Frontend

**Owner**: M5  
**Estimated Effort**: 60-80 hours  
**Status**: ⏳ MINIMAL (health check only)

#### Phase 1: REST API (Week 2 start-mid)
- [ ] Create `backend/app/api/routes.py`
- [ ] Implement `/api/v1/lineage/{entity_id}`
- [ ] Implement `/api/v1/lineage/as_of` with temporal params
- [ ] Connect to M3 PostgreSQL queries
- [ ] Error handling, validation
- [ ] Write API tests

**Deliverable**: Full `/api/v1` endpoints (8-10 routes)

#### Phase 2: Basic Frontend (Week 2 mid-late)
- [ ] Create React/Vue project structure
- [ ] Implement lineage explorer screen
- [ ] Add time controls (valid_at, known_as_of)
- [ ] Call M5 API endpoints
- [ ] Display lineage table/graph

**Deliverable**: Stage 1 UI (explorer, time controls, evidence panel)

---

## 18. Tomorrow's Demo

### What to Demonstrate

#### ✅ SHOW THESE (They Work)

1. **M1: SQL Parsing Demo**
   ```bash
   python -m pytest tests/test_static_corpus.py::test_case_when_condition_and_branch_columns -v
   ```
   **Show**: SQL → SQLGlot → StaticEvidence extraction

2. **M3: Temporal Queries Demo**
   ```bash
   python -m pytest tests/test_temporal_oracle.py::test_visible -v
   ```
   **Show**: Bitemporal query logic (valid_at + known_as_of)

3. **M4: Reasoning Engine Demo**
   ```bash
   python test_demo.py
   ```
   **Show**: End-to-end pipeline (static + runtime → predictions)

4. **Test Results**
   ```bash
   python -m pytest -q
   ```
   **Show**: 63 tests passing (no failures)

5. **Architecture Overview**
   **Show**: Repository structure, module ownership, data flow diagram

---

### ❌ DO NOT CLAIM

- ❌ "Runtime evidence is working" (M2 not implemented)
- ❌ "Ground truth is ready" (spike pending)
- ❌ "API is complete" (only health check)
- ❌ "UI is ready" (not started)
- ❌ "This proves the research hypothesis" (mock data only)
- ❌ "ProvSQL is integrated" (unknown feasibility)

---

### 📌 Likely Questions & Honest Answers

**Q: What is data lineage?**  
A: Tracking which data flows into which transformations. Example: "salary column → CASE WHEN → adjusted_salary column"

**Q: Why bitemporal?**  
A: Business logic changes over time (valid_time). We also learn about past events over time (transaction_time). Both matter.

**Q: Why SQLGlot?**  
A: SQL parsing library. Converts SQL → Abstract Syntax Tree → identifies column dependencies.

**Q: Why PostgreSQL + Neo4j?**  
A: PostgreSQL = immutable history authority. Neo4j = optional fast graph queries (not implemented yet).

**Q: What is "incomplete runtime evidence"?**  
A: Events get lost. Instrumenting all code is hard. We can't assume "no event" means "no dependency".

**Q: How do you distinguish "didn't happen" vs "we didn't see"?**  
A: Using coverage awareness (ProvSQL spike pending) + static analysis. If static says it's possible AND we have complete coverage AND saw nothing → REFUTED. Otherwise → POSSIBLE.

**Q: Why mock data?**  
A: Can't prove the research hypothesis yet. Need real ground truth (ProvSQL). Mock data shows architecture works.

**Q: When is the API ready?**  
A: Week 2. M5 is implementing `/api/v1` endpoints for lineage queries.

**Q: When is the UI ready?**  
A: Week 2 for Stage 1 (explorer + time controls). Not all features.

**Q: What happens with unsupported SQL?**  
A: Marked as UNSUPPORTED. Parser returns ParserStatus. Engine treats as UNKNOWN (can't reason about it).

**Q: Where is the ProvSQL integration?**  
A: Pending spike (M2, Week 2). Testing if ProvSQL can give column-level ground truth.

---

## 19. Known Limitations

### M1: SQLGlot
- ❌ Cannot handle OUTER JOINs (LEFT, RIGHT, FULL) - marked UNSUPPORTED
- ❌ Cannot handle window functions - marked UNSUPPORTED
- ❌ Cannot handle UDFs (user-defined functions) - marked UNSUPPORTED
- ❌ Cannot handle dynamic SQL - marked UNSUPPORTED
- ⚠️ Requires schema - will reject if schema missing
- ⚠️ Alias resolution: resolves to real table names (not kept as aliases)

### M2: Runtime Evidence
- ❌ NOT IMPLEMENTED - only framework
- ❌ ProvSQL feasibility UNKNOWN
- ❌ OpenLineage event schema not finalized
- ⚠️ Column-level vs dataset-level granularity TBD

### M3: Temporal Storage
- ✅ Schema complete, works
- ⚠️ No actual PostgreSQL data loaded yet (mock only)
- ⚠️ No query optimization (assumes small dataset)
- ⚠️ Unknown effective time handling (TBD)

### M4: Reasoning
- ⚠️ Tested only on mock data (w03_case_when fixture)
- ⚠️ No real SQL, no real runtime events
- ⚠️ Coverage derivation method TBD
- ⚠️ Loss simulation not yet integrated

### M5: API & UI
- ❌ NO API ENDPOINTS IMPLEMENTED (only /health)
- ❌ NO UI SCREENS IMPLEMENTED
- ❌ NO DATABASE INTEGRATION YET

### Project-Wide
- ⚠️ No actual data ingestion pipeline (M2 pending)
- ⚠️ No Neo4j projection (marked optional)
- ⚠️ No performance measurements
- ⚠️ No production deployment support
- ⚠️ No authentication/authorization

---

## 20. Known Bugs / TODOs

### Code TODOs

**From README.md**:
- [ ] R0 (temporal filtering) needs explicit definition
- [ ] PARTIAL static semantics vs REFUTED_FOR_RUN conflict needs review
- [ ] Coverage derivation method (D-09) pending
- [ ] Positive runtime evidence definition (D-10) pending
- [ ] Ground-truth semantics (D-11) pending

**From Codebase**:
- None found in M1, M3, M4 (complete)
- M2, M5 are framework/stubs (expected)

### Known Issues

- **API test skip**: API tests skipped until `pip install fastapi httpx`
- **Import boundary check**: Working (enforces ground truth isolation)
- **Leakage tests**: All passing (ground truth protected)

---

## 21. Testing Status

### Test Summary

```
65 tests total
├─ 63 PASSED ✅
├─ 2 SKIPPED (need fastapi)
└─ 0 FAILED
```

### Test Breakdown by Member

| Member | Module | Tests | Status | Evidence |
|--------|--------|-------|--------|----------|
| **M1** | SQL lineage | 31 | ✅ PASS | `tests/test_static_*.py` |
| **M3** | Temporal + Identity | 31 | ✅ PASS | `tests/test_temporal_*.py`, `test_identity.py` |
| **M4** | Reasoning + Metrics | 32 | ✅ PASS | `tests/test_engine_*.py`, `test_baselines.py`, `test_metrics.py` |
| **Leakage** | Import isolation | 4 | ✅ PASS | `tests/test_leakage.py` |
| **Fixtures** | Mock data | 4 | ✅ PASS | `tests/test_fixtures_plumbing.py` |
| **API** | FastAPI | 3 | ⏳ SKIP | `tests/test_api_slice.py` (needs fastapi) |

### Running Tests

```bash
# All tests
python -m pytest -q

# M1 tests only
python -m pytest tests/test_static_*.py -v

# M3 tests only
python -m pytest tests/test_temporal_oracle.py tests/test_identity.py -v

# M4 tests only
python -m pytest tests/test_engine_rules.py tests/test_baselines.py tests/test_metrics.py -v

# With coverage (requires pytest-cov)
python -m pytest --cov=contracts --cov=ingestion --cov=backend --cov=research --cov-report=html
```

---

## 22. Commands to Run the Project

### Setup

```bash
cd data-lineage-engine

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install pytest

# Optional: For API testing
pip install fastapi httpx

# Optional: For coverage reports
pip install pytest-cov
```

### Verification

```bash
# Check import boundaries
python scripts/check_import_boundaries.py

# Run all tests
python -m pytest -q

# Run specific test file
python -m pytest tests/test_static_corpus.py -v

# Run demo
python test_demo.py
```

### Backend (Week 2)

```bash
# When M5 implements API:
pip install fastapi uvicorn

# Start API server (from repository root)
uvicorn backend.app.main:app --reload --port 8000

# Test API
curl http://localhost:8000/health
```

### Frontend (Week 2)

```bash
# When M5 implements UI:
cd frontend
npm install
npm start  # Runs on http://localhost:3000
```

### Database (Week 2 - M3 support)

```bash
# When M2 implements ETL:
psql -U postgres -d kairos -f backend/migrations/0001_core.sql
python scripts/seed_data.py  # To be created
```

---

## 23. Important Files

### Architecture & Documentation

| File | Size | Owner | Purpose |
|------|------|-------|---------|
| `docs/FINAL_ARCHITECTURE_AND_RESEARCH_EXECUTION_PACK.md` | 164 KB | M4 | Complete specification |
| `docs/TEAM_GUIDE.md` | 50 KB | M4 | Week 1 setup guide |
| `docs/DATA_MODEL.md` | 15 KB | M3 | PostgreSQL schema docs |
| `README.md` | 3 KB | Team | Project overview |

### Core Implementation

| File | Lines | Owner | Purpose |
|------|-------|-------|---------|
| `contracts/types.py` | 210 | M4 | Enums, dataclasses |
| `contracts/evidence.py` | 445 | M4 | Evidence types, Prediction |
| `contracts/interfaces.py` | 212 | M4 | Abstract interfaces |
| `ingestion/sql/parser.py` | 490 | M1 | SQLGlot integration |
| `backend/app/temporal/reference.py` | 89 | M3 | Temporal oracle |
| `backend/app/identity/canonical_ids.py` | 257 | M3 | ID canonicalization |
| `research/reasoning/engine.py` | 360 | M4 | FourStateEngine |
| `research/baselines/baselines.py` | 380 | M4 | B1-B5 baselines |
| `research/metrics/metrics.py` | 280 | M4 | Metric calculations |
| `backend/migrations/0001_core.sql` | 232 | M3 | PostgreSQL schema |

### Tests

| File | Tests | Owner | Coverage |
|------|-------|-------|----------|
| `tests/test_static_corpus.py` | 12 | M1 | SQL parsing |
| `tests/test_static_alias_resolution.py` | 6 | M1 | Alias handling |
| `tests/test_static_fingerprints.py` | 4 | M1 | Fingerprinting |
| `tests/test_static_unsupported.py` | 9 | M1 | Unsupported SQL |
| `tests/test_temporal_oracle.py` | 13 | M3 | Temporal queries |
| `tests/test_identity.py` | 18 | M3 | ID canonicalization |
| `tests/test_engine_rules.py` | 20 | M4 | R1-R5 rules |
| `tests/test_baselines.py` | 5 | M4 | B1-B5 correctness |
| `tests/test_metrics.py` | 3 | M4 | Metric calculations |
| `tests/test_leakage.py` | 4 | M4 | Ground truth isolation |

---

## 24. Important Technical Decisions

### LOCKED (Cannot change without decision record)

1. **PostgreSQL is the only authority** (CR-02)
   - Neo4j is optional projection only
   - All truth comes from PostgreSQL
   - Immutable raw event log

2. **Ground truth never enters predictor** (CR-01, CR-06)
   - Four-layer leakage protection
   - Import boundary enforced by CI
   - Predictors never see actual truth

3. **Bitemporal design** (valid_time + transaction_time) (DL-05)
   - Two time dimensions kept separate
   - Enables historical reconstruction queries
   - Half-open intervals [lo, hi)

4. **Four-state vocabulary** (DL-06)
   - OBSERVED, REFUTED_FOR_RUN, POSSIBLE, UNKNOWN
   - Maps to established certain/possible/unknown semantics

5. **M1-M5 Team Split** (DL-13)
   - M1: SQL lineage
   - M2: Runtime evidence
   - M3: Storage
   - M4: Reasoning
   - M5: API/UI

6. **No outer joins** in initial SQL support (architectural)
   - LEFT/RIGHT/FULL joins marked UNSUPPORTED
   - Can be added later

7. **Import boundaries** (CI enforced)
   - Reasoning ≠ Ground truth
   - Ground truth ≠ Ingestion
   - Research ≠ Backend

### PENDING TEAM DECISION (Open)

| ID | Decision | Owner | Deadline |
|----|----------|-------|----------|
| D-03 | Olist license verification | M2+M5 | Before dataset committed |
| D-09 | How coverage is derived | M2+M4 | Before pilot |
| D-10 | What counts as positive runtime evidence | M2+M4 | Week 2 |
| D-11 | Ground-truth semantics (where vs why provenance) | M2+M4 | After spike |
| D-12 | Prediction unit universe (which dependencies to enumerate) | M4+M1 | Before pilot |

---

## 25. Questions Claude Should Ask Before Making Major Changes

Before implementing Week 2 features, Claude should ask:

1. **Architecture Impact**: Does this change violate import boundaries or leakage rules?
2. **Team Ownership**: Which member owns this module? Will changes break their interface?
3. **Contract Changes**: Does this require changes to `contracts/`? (Needs all-member review)
4. **Existing Work**: What existing code does this build on? Have you read it?
5. **Test Coverage**: Are there existing tests for the module you're changing?
6. **Backward Compatibility**: Will this break existing M1/M3/M4 code?
7. **Mock vs Real**: Is this for mock/demo or production? Are you labeling it correctly?
8. **Performance**: Have measurements been made, or is this premature optimization?
9. **Decision Records**: Is this resolving an open decision (D-03, D-10, D-11, etc.)?
10. **Demo Impact**: Will this break the tomorrow demo?

---

## 26. Rules for Future Implementation

### During Week 2, Follow These Rules

#### Code Quality
- ✅ Write tests before or immediately after implementation
- ✅ Preserve existing passing tests
- ✅ Run `python scripts/check_import_boundaries.py` before commit
- ✅ Label mock/demo/PLUMBING data clearly
- ✅ Never claim anything from mock data is a research result

#### Architecture
- ✅ Respect M1-M5 ownership boundaries
- ✅ Keep PostgreSQL as the authority (no Neo4j without measurement)
- ✅ Keep ground truth isolated from predictors
- ✅ Never import contracts.truth from reasoning or baselines code

#### API Design
- ✅ All M5 routes should start with `/api/v1`
- ✅ Use canonical IDs (CanonicalID) not raw names
- ✅ Always include temporal context (valid_at, known_as_of)
- ✅ Return structured error responses

#### Documentation
- ✅ Update `docs/` if architecture changes
- ✅ Document decisions in decision log
- ✅ Keep README.md in sync with actual status
- ✅ Document limitations honestly

#### Testing
- ✅ Each member tests their own module first
- ✅ Run integration tests before PR
- ✅ Test both supported and unsupported cases
- ✅ Test error conditions

#### Git/Workflow
- ✅ Work on `feature/member-N` branches (not main)
- ✅ Create pull requests with clear descriptions
- ✅ Get code owner review before merging
- ✅ Small commits over giant ones

---

## 27. Demo Readiness Checklist (Tomorrow)

- [x] M1: SQL parsing tests pass (31 tests)
- [x] M3: Temporal queries tests pass (31 tests)
- [x] M4: Reasoning engine tests pass (32 tests)
- [x] `test_demo.py` runs successfully
- [x] Import boundaries enforced (`check_import_boundaries.py`)
- [ ] Presentation slides ready
- [ ] Architecture diagram printed/shared
- [ ] Expected questions reviewed
- [ ] Honest limitations discussed
- [ ] Week 2 plan communicated

---

## 28. Appendix: Glossary

| Term | Definition |
|------|-----------|
| **Bitemporal** | Two time dimensions: valid_time (reality) + transaction_time (knowledge) |
| **Lineage** | Data flow: which columns/tables feed into which transformations |
| **Evidence** | Observable facts about lineage (static from SQL, runtime from events) |
| **PredictorInput** | Bundle of static + runtime evidence for reasoning engine |
| **Four States** | OBSERVED, REFUTED_FOR_RUN, POSSIBLE, UNKNOWN |
| **Coverage** | Did we instrument everything? Can we trust negative results? |
| **PLUMBING** | Demo/test code using mock data, not research results |
| **Canonical ID** | Globally unique identifier for dataset/column (7-tuple) |
| **as_of** | Temporal query: "Show lineage as of DATE, knowing about DATE2" |
| **valid_time** | When the lineage was true in business reality |
| **transaction_time** | When we recorded our knowledge of the lineage |

---

## INSTRUCTIONS FOR CLAUDE

### How to Use This Document

1. **Read this file first** before touching the codebase
2. **Treat this as your source of truth** for what's implemented vs planned
3. **When making changes**, reference the specific files and line numbers
4. **Never claim functionality** unless you verify it in the code

### When Implementing Week 2 Features

#### Before You Start
1. Read the section for that member (M2 or M5)
2. Check the ownership matrix
3. Review any existing interfaces/tests
4. Verify import boundaries won't be violated
5. Ask clarifying questions if anything is unclear

#### During Implementation
1. Run tests after each meaningful change
2. Preserve existing passing tests
3. Label mock data as PLUMBING/mock
4. Update documentation if you change architecture
5. Commit frequently with clear messages

#### Before PR
1. Run full test suite: `python -m pytest -q`
2. Run boundary check: `python scripts/check_import_boundaries.py`
3. Verify related tests still pass
4. Write test for your new code

#### Special Rules
- **Never import `contracts.truth` into reasoning/baselines code**
- **Never put ground truth into PredictorInput**
- **Always use canonical IDs in API routes** (not raw names)
- **Never claim mock results are research results**
- **Always include temporal context in queries**

### If You Find Discrepancies

**Between this document and the code**:
- Trust the code (it's the source of truth)
- Update this document
- Ask for clarification

**Between the documentation and code**:
- Both are wrong or outdated
- Read the architecture pack (docs/FINAL_*.md) for intent
- Ask team for decision

**If something is unclear**:
- Ask explicitly before implementing
- Don't guess
- Reference this document and the code

### Recommended Reading Order

For a new developer on the team:

1. This file (sections 1-8)
2. `README.md` (project overview)
3. `docs/TEAM_GUIDE.md` (Week 1 setup)
4. Your specific member section (12-18)
5. Relevant code files
6. `docs/FINAL_ARCHITECTURE_AND_RESEARCH_EXECUTION_PACK.md` (full spec)

---

**Document Generated**: Week 1 End  
**Last Updated**: Today  
**Status**: Accurate for current implementation state  
**Next Review**: End of Week 2

