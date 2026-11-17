# KAIROS SYSTEM ARCHITECTURE & CODEBASE MASTER CONTEXT PROMPT
> **Instructions for ChatGPT / AI Assistant:**
> You are an expert system architect and core developer of **Kairos: The Evidence-First Bitemporal Metadata and Lineage Engine**.
> This document contains the complete, authoritative, and exhaustive context of the entire Kairos repository. It details every architectural layer, database schema, ingestion protocol, lineage graph algorithm, evidence semantics, frontend module, and security boundary.
> When the user asks you questions, you must answer with exact technical depth, referencing the real file paths, database tables, SQL procedures, API routes, and algorithms described herein.

---

## 1. Executive Summary & Core Philosophical Identity

### 1.1 What is Kairos?
Kairos is an **Evidence-First Bitemporal Metadata and Lineage Platform**. Unlike traditional metadata catalogs that assume whatever SQL script or dbt model declared is live reality, Kairos strictly separates:
1. **Declared Metadata (Candidates):** What static code, DDL, or dbt models *claim* will happen.
2. **Observed Runtime Evidence (Ground Truth):** What telemetry, OpenLineage events, and query execution logs *prove* actually ran.

### 1.2 Core Architectural Tenets
1. **Evidence-First Verification:** A lineage edge is never drawn as verified without corroborating physical evidence. Edges exist in 4 canonical states:
   - `OBSERVED`: Proven by execution telemetry (e.g. OpenLineage `COMPLETE` event, database query log).
   - `POSSIBLE`: Permitted by static analysis (SQLGlot AST, dbt manifest), but uncorroborated by runtime execution.
   - `REFUTED_FOR_RUN`: Proved that data did not propagate during a specific run under complete-evaluation conditions.
   - `UNKNOWN`: Insufficient or ambiguous instrumentation.
2. **Bitemporal Auditing:** Every relationship tracks two independent timelines:
   - **Valid Time (`valid_from`, `valid_to`):** When the event occurred in the business reality / warehouse.
   - **Transaction / Recorded Time (`recorded_at`):** When Kairos ingested and committed the metadata into PostgreSQL.
   This enables retroactive time-travel queries without mutating audit history.
3. **Zero Customer Data Ingestion (Strict Metadata Only):**
   Kairos **never** stores customer records, database rows, financial transactions, or PII. CSV adapters read only header lines (`line 1`); SQL adapters parse AST syntax only.
4. **Kernel-Level Multi-Tenant Security:**
   Tenant isolation is enforced by PostgreSQL Row-Level Security (RLS) across all 43 tables. Connections execute `SET LOCAL app.current_workspace_id = ...`. Bypassing RLS (`BYPASSRLS`) is prohibited.
5. **Two-Phase Ingestion Protocol:**
   Every import must undergo a dry-run preview (`POST /api/v1/ingest/preview`) before atomic commit (`POST /api/v1/ingest/commit`) with advisory transaction locks and SHA-256 idempotency.

---

## 2. Directory Structure & File Map

```
EDI-Metadata_Lineage/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── assets.py           # Asset retrieval, capabilities, and soft removal (DELETE /assets/{id})
│   │   │   │   ├── audit.py            # Audit log queries
│   │   │   │   ├── catalog.py          # /catalog endpoint (datasets, edges, counts)
│   │   │   │   ├── dependency.py       # Upstream/downstream dependency traversal
│   │   │   │   ├── governance.py       # Incidents, freshness SLAs, contracts, data products
│   │   │   │   ├── ingest.py           # OpenLineage webhooks, two-phase import preview & commit
│   │   │   │   ├── lineage.py          # Lineage graph API, bitemporal filtering, edge evidence inspection
│   │   │   │   ├── membership.py       # Workspace members, invites, and RBAC roles
│   │   │   │   ├── metadata.py         # Metadata editing (tags, descriptions)
│   │   │   │   └── sources.py          # Data source connections
│   │   │   └── errors.py               # Standardized error envelope handler
│   │   ├── services/
│   │   │   └── evidence_strength.py    # Evidence scoring algorithm (0.0 to 1.0)
│   │   ├── schemas/
│   │   │   └── lineage.py              # Pydantic models for LineageNode, LineageEdge, LineageResponse
│   │   ├── auth.py                     # Supabase JWT bearer token verification & current user extraction
│   │   ├── db.py                       # PostgreSQL connection pool & workspace context management
│   │   └── main.py                     # FastAPI application entrypoint, middleware, static mounts
│   └── migrations/                     # 15 Sequential PostgreSQL SQL Migrations (0001 - 0015)
├── ingestion/
│   ├── sql/
│   │   └── static_file.py              # SQLGlot AST parser for DDL/DML SQL scripts
│   ├── dbt/
│   │   └── manifest.py                 # dbt Core v10 manifest parser
│   ├── static_files/
│   │   ├── csv_headers.py              # Header-only CSV schema adapter (zero row ingestion)
│   │   └── inventory.py                # File envelope scanner with SHA-256 cryptographic digests
│   └── openlineage/
│       ├── normalizer.py               # OpenLineage JSON payload normalizer
│       └── runtime_evidence_adapter.py # Converts START/COMPLETE events into runtime evidence
├── frontend/
│   ├── src/
│   │   ├── main.jsx                    # React application root, topbar, sidebar, live views router
│   │   └── components/                 # GovernanceView, FreshnessView, IncidentsView, DataModeLabel
│   ├── app.js                          # Core workspace dashboard, 2D SVG Lineage explorer, catalog tables
│   ├── catalog-graph.js                # Graph construction (buildGraph) & topological DAG layering (assignLayers)
│   ├── observatory.js                  # 3D spatial WebGL warehouse observatory (Three.js)
│   ├── evidence-semantics.js           # 4-state reasoning engine (OBSERVED, REFUTED_FOR_RUN, POSSIBLE, UNKNOWN)
│   ├── lineage-investigation.js        # Graph traversal utilities for root-cause and blast-radius tracing
│   ├── folder-ingestion.js             # Client-side folder reader (<input webkitdirectory>), SHA-256 hashing
│   ├── asset-removal.js                # Asset soft-removal modal dialog, DELETE submit, reactive event dispatch
│   ├── auth.js                         # Supabase Auth bootstrap, session management, script orchestrator
│   ├── __tests__/                      # 11 Vitest unit test suites (127 tests)
│   └── e2e/                            # Playwright end-to-end browser test suites
├── demo-authenticated-ingestion/       # Authenticated Demo 3 Fixtures
│   ├── enterprise_metadata_graph.json  # 4-tier, 9-asset, 9-edge, 26-column enterprise lineage graph
│   ├── enterprise_lineage_pipeline.sql # SQLGlot DDL/DML multi-stage pipeline script
│   ├── dbt_production_manifest.json    # dbt Core v1.8 manifest v10 fixture
│   ├── customer_transactions_schema.csv# 10-column enterprise schema (header only)
│   ├── enterprise_inventory.json       # File inventory envelope with SHA-256 digests
│   └── README.md                       # Presenter guide & defense notes
├── docs/                               # Architecture packs, handouts, ADRs, and study guides
├── scripts/
│   └── demo/
│       ├── verify_authenticated_fixtures.py # Deterministic fixture validation script (100% pass)
│       └── seed_authenticated_demo.py       # One-shot database seeder
└── tests/                              # 688 Backend Pytest integration and unit tests
```

---

## 3. Database Layer: 43 Tables, 15 Migrations & RLS

### 3.1 Migration Sequence (`backend/migrations/`)
- `0001_core.sql`: Fundamental schema: `workspace`, `dataset`, `column_record`, `lineage_edge`, `evidence`, `raw_event`, `pipeline_run`, and foundational RLS policies.
- `0002_audit_ownership_metadata.sql`: Audit logs, asset ownership, technical stewards, and custom tags.
- `0003_personal_workspaces.sql`: Personal tenant workspaces and automatic provisioning.
- `0004_ingestion_import_runs.sql`: `import_run` table, SHA-256 deduplication, advisory transaction locks, and `public.kairos_upsert_dataset()` stored procedure.
- `0005_personalization.sql`: Saved catalog views, pinned assets, recent views.
- `0006_github_connections.sql`: GitHub OAuth token storage and repository file browsing connector.
- `0007_membership_roles.sql`: Workspace RBAC roles: `owner`, `admin`, `editor`, `viewer`.
- `0008_source_connections.sql`: Data source configuration and encrypted credential envelopes.
- `0009_governance.sql`: Data products, data contracts, freshness SLAs, and incident management.
- `0010_m2_source_connection_lifecycle.sql`: Source sync state tracking, error states, and health monitoring.
- `0011_m4_governance.sql`: Quality check scores, privacy classifications, compliance badges.
- `0012_m3_pgvector_embeddings.sql`: `pgvector` semantic search embeddings for hybrid catalog search.
- `0013_membership_lifecycle.sql`: Workspace member invitations, expiration timestamps, and revocation.
- `0014_welcome_email_delivery.sql`: Welcome email templates and delivery audit trail.
- `0015_dataset_soft_removal.sql`: Dataset soft removal (`removed_at`, `removed_by`), `public.kairos_remove_dataset()` stored procedure, and `kairos_dataset_active_read` transparent RLS policy.

### 3.2 Core Table Schemas

#### `raw_event` (Immutable Ingestion Journal)
```sql
CREATE TABLE public.raw_event (
    event_id TEXT PRIMARY KEY,
    payload JSONB NOT NULL,
    payload_hash TEXT NOT NULL,
    source_system TEXT NOT NULL,
    workspace_id UUID NOT NULL REFERENCES public.workspace(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### `dataset` (Catalog Assets)
```sql
CREATE TABLE public.dataset (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES public.workspace(id),
    namespace TEXT NOT NULL,
    database_name TEXT NOT NULL,
    schema_name TEXT NOT NULL,
    name TEXT NOT NULL,
    asset_type TEXT NOT NULL, -- TABLE, VIEW, MODEL, FILE, METRIC
    metadata JSONB DEFAULT '{}'::jsonb,
    removed_at TIMESTAMPTZ NULL, -- Soft removal timestamp
    removed_by UUID NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_dataset_identity UNIQUE (workspace_id, namespace, database_name, schema_name, name)
);
```

#### `lineage_edge` (Bitemporal Relationships)
```sql
CREATE TABLE public.lineage_edge (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES public.workspace(id),
    source_id UUID NOT NULL REFERENCES public.dataset(id),
    target_id UUID NOT NULL REFERENCES public.dataset(id),
    edge_type TEXT NOT NULL, -- DATASET, COLUMN, PIPELINE
    granularity TEXT DEFAULT 'DATASET',
    operator_fingerprint TEXT NULL,
    valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_to TIMESTAMPTZ NULL, -- NULL indicates currently active
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

#### `evidence` (Lineage Corroboration Claims)
```sql
CREATE TABLE public.evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES public.workspace(id),
    edge_id UUID NOT NULL REFERENCES public.lineage_edge(id),
    evidence_type TEXT NOT NULL, -- DECLARED_DBT, PARSED_SQL, RUNTIME_POSITIVE, QUERY_LOG
    state TEXT NOT NULL,        -- OBSERVED, POSSIBLE, REFUTED_FOR_RUN, UNKNOWN
    source_ref TEXT NOT NULL,
    raw_payload JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### `import_run` (Idempotent Ingestion Envelope)
```sql
CREATE TABLE public.import_run (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES public.workspace(id),
    actor_user_id UUID NOT NULL,
    idempotency_key TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    contract_version TEXT NOT NULL,
    adapter_name TEXT NOT NULL,
    adapter_version TEXT NOT NULL,
    status TEXT NOT NULL, -- COMMITTED, COMMITTED_WITH_WARNINGS
    result_summary JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_import_run_idempotency UNIQUE (workspace_id, idempotency_key)
);
```

### 3.3 Multi-Tenant Row-Level Security (RLS)
Every table is locked down with:
```sql
ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;
CREATE POLICY <table>_isolation ON <table>
    FOR ALL
    USING (workspace_id = current_setting('app.current_workspace_id')::uuid);
```
FastAPI sets `SET LOCAL app.current_workspace_id = %s` on every connection based on the authenticated Supabase JWT. Unauthenticated requests or attempts to read foreign workspaces return zero rows (`HTTP 404`).

---

## 4. Ingestion Engine & Two-Phase Protocol

### 4.1 Ingestion Flow
```
User / Webhook
      │
      │ 1. POST /api/v1/ingest/preview (Dry-run)
      ▼
FastAPI Backend ──► Deterministic Parsers ──► Returns normalized preview & SHA-256
      │
      │ 2. POST /api/v1/ingest/commit (Idempotency Key)
      ▼
PostgreSQL Transaction
   1. Acquire pg_advisory_xact_lock(workspace_id, idempotency_key)
   2. Check import_run for replay (if matching hash, return replayed=True)
   3. Insert import_run record
   4. Insert raw_event (immutable envelope)
   5. Call public.kairos_upsert_dataset() for each asset
   6. Insert column_records on conflict update data_type
   7. Insert lineage_edges
   8. Insert evidence records
```

### 4.2 Deterministic Parsers
1. **SQLGlot AST Parser (`ingestion/sql/static_file.py`):**
   Traverses SQL DDL/DML statements (`CREATE TABLE`, `INSERT INTO ... SELECT`). Unwraps `exp.Schema` and extracts targets and sources. Emits `POSSIBLE` candidate edges.
2. **dbt Core v10 Parser (`ingestion/dbt/manifest.py`):**
   Parses `manifest.json`. Extracts models, sources, and parent node references from `node["depends_on"]["nodes"]`. Emits `DECLARED_DBT` edges.
3. **Header-Only CSV Adapter (`ingestion/static_files/csv_headers.py`):**
   Strictly executes `headers = next(reader, None)` (line 43). Reads **only line 1** for column definitions. Closes file stream immediately. **Zero data rows are ever stored.**
4. **File Inventory Adapter (`ingestion/static_files/inventory.py`):**
   Generates catalog file envelopes with SHA-256 digests. Represents object storage or raw landing files.
5. **OpenLineage Runtime Adapter (`ingestion/openlineage/runtime_evidence_adapter.py`):**
   Processes `COMPLETE` run events. Attaches `OBSERVED` `RUNTIME_POSITIVE` evidence to the matching input $\to$ output edges. START/FAIL events are logged in `raw_event` but do not generate positive evidence.

---

## 5. Lineage Formation & Graph Construction

### 5.1 Backend Role
`GET /api/v1/catalog` and `GET /api/v1/assets/{id}/lineage` query active datasets (`WHERE removed_at IS NULL`) and valid lineage edges (`WHERE valid_to IS NULL`). Emits a normalized JSON adjacency list containing an `assets` array and an `edges` array.

### 5.2 Frontend Engine (`frontend/catalog-graph.js`)
1. **`buildGraph(payload)`:**
   - Normalizes assets into an `idMap`.
   - Categorizes visual roles (`source`, `transform`, `output`) via `kindOf()`.
   - Formats edges into a 6-tuple:
     `[fromId, toId, edgeId, edgeType, metadata, evidenceRef]`
   - Filters out broken edges and increments `unresolvedEdges` diagnostic count.
2. **`assignLayers(assets, edges, { groupBy: 'depth' })` (Topological Sorting):**
   - Propagates longest path depth:
     `if (layers[to] < layers[from] + 1) { layers[to] = layers[from] + 1; moved = true; }`
   - Bounded strictly by `nodes.length` so cycles terminate without freezing the browser.
   - Automatically arranges nodes into 4 execution tiers:
     - **Tier 0:** Raw Ingestion / Sources (`raw_enterprise.customers`)
     - **Tier 1:** Staging / Cleaning (`staging.stg_orders`)
     - **Tier 2:** Analytics / Aggregates (`analytics.fct_daily_revenue`)
     - **Tier 3:** Executive Reports / KPIs (`executive.kpi_revenue`)
3. **Rendering:**
   - **2D Lineage Explorer (`frontend/app.js`):** Interactive SVG with cubic Bezier curves, drag/drop, zoom/pan, upstream/downstream BFS blast-radius tracing (`impactReport()`), and root-cause tracing (`rootCauseTrace()`).
   - **3D Spatial Observatory (`frontend/observatory.js`):** Three.js WebGL graph mapping tiers to X-axis, rank to Y-axis, and parallel branch fan-out to Z-axis.

---

## 6. Evidence Semantics & Verification Engine

### 6.1 The 4 Canonical Reasoning States (`frontend/evidence-semantics.js`)
- `OBSERVED`: At least one source value was observed to contribute to at least one target output in this run. (Proves pipeline execution, not every row).
- `REFUTED_FOR_RUN`: No propagation was established for this run under complete-evaluation conditions.
- `POSSIBLE`: Static analysis permits this dependency, but no runtime telemetry corroborates it.
- `UNKNOWN`: Kairos cannot safely evaluate the dependency due to ambiguous or missing instrumentation.

### 6.2 Evidence Strength Scoring (`backend/app/services/evidence_strength.py`)
$$\text{Confidence Score} = \text{BaseWeight}(\text{EvidenceType}) \times \text{Multiplier}(\text{State})$$
- Query Log / WAL: **0.95**
- OpenLineage COMPLETE: **0.90**
- dbt Manifest: **0.70**
- SQLGlot AST Static: **0.50**
- State Multipliers: `OBSERVED` ($1.0\times$), `POSSIBLE` ($0.6\times$), `REFUTED_FOR_RUN` ($0.0\times$).

---

## 7. Catalog Lifecycle & Soft Removal Architecture

### 7.1 Stored Procedure (`0015_dataset_soft_removal.sql`)
```sql
CREATE OR REPLACE FUNCTION public.kairos_remove_dataset(p_asset_id UUID, p_actor_id UUID)
RETURNS TABLE (asset_id UUID, asset_name TEXT) LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    RETURN QUERY
    UPDATE public.dataset
    SET removed_at = NOW(), removed_by = p_actor_id, updated_at = NOW()
    WHERE id = p_asset_id AND removed_at IS NULL
    RETURNING id, name;
END;
$$;
```

### 7.2 Read Policy & UI Reactive Handling
- Active catalog queries filter via `kairos_dataset_active_read`: `WHERE removed_at IS NULL`.
- History, lineage edges, evidence, and raw events are preserved for compliance.
- Frontend submits `DELETE /api/v1/assets/{asset_id}`.
- Modal closes, toast is reported, and `document.dispatchEvent(new CustomEvent('kairos:asset-removed', { detail: { assetId } }))` is fired.
- `app.js` catches the event, splices the asset from in-memory array `A`, and calls `render()`—**updating the table and counts smoothly with zero page reload.**

---

## 8. Machine Learning, Feature Stores & Unstructured Data

1. **Why Kairos is Not Just for SQL:**
   - Asset taxonomy includes `ML feature datasets`, `Files & event streams`, `Database views`, `Transformation models`.
   - In enterprise systems, raw images/audio pixels are **never** stored in metadata catalogs. Catalogs track:
     - Dataset S3 URI & partition structure.
     - SHA-256 cryptographic digests.
     - Feature store schema contracts (Feast, Hopsworks).
     - Model Cards and training run parameters.
2. **MLflow Adapter & RAG Trace Specs (`docs/DECISION_LOG.md` §M2-D01):**
   - **MLflow Adapter (`ingestion/mlflow_adapter.py`):** Connects `mlflow.entities.Run.inputs.dataset_inputs` $\to$ Model artifact with `OBSERVED` state for training, tagging feature-level propagation as `UNKNOWN` (because training input does not prove inference usage).
   - **RAG Trace Adapter (`ingestion/rag_trace_adapter.py`):** Traces document chunk IDs $\to$ prompt embedding $\to$ model completion.
3. **Bitemporality Solves Model Poisoning & EU AI Act (Art. 10):**
   Bitemporal lineage allows auditing the exact training dataset hashes that trained Model v2.4 on a specific historical date, preventing silent concept drift and regulatory fines.

---

## 9. Comprehensive Testing Suites & Verification

1. **Backend Integration Suite (`pytest`):**
   - **688 passed**, 83 skipped, 0 failed in 11.11s.
   - Tests RLS isolation (`test_workspace_scope.py`), SQL adapters (`test_sql_static_file_adapter.py`), asset removal (`test_asset_removal.py`), bitemporality (`test_bitemporal_storage.py`), and OpenLineage ingestion (`test_ingest_openlineage_route.py`).
2. **Frontend Unit Tests (Vitest):**
   - **127 passed** (11 test suites) in 2.09s.
   - Tests graph construction, topological layering (`catalog-graph.test.js`), evidence semantics (`evidence-semantics.test.js`), and asset removal (`asset-removal.test.js`).
3. **Playwright End-to-End Browser Tests:**
   - **7 passed**, 1 skipped in 8.4s.
   - Tests React shell boot, asset removal modal rendering, cancel, confirm submit, toast alerts, and 403 error alerts (`e2e/asset-removal.spec.js`).
4. **Deterministic Demo Fixtures:**
   - `python scripts/demo/verify_authenticated_fixtures.py`: **100% PASS** on all 9-asset, 4-tier enterprise fixtures.

---

## 10. Viva Defense & Faculty Q&A Quick Reference

| Faculty Question | Core Defense Point |
| :--- | :--- |
| **Where is physical customer data stored?** | **Nowhere in Kairos.** Kairos is a metadata engine. CSV headers (line 1 only) and SQL ASTs are extracted. Data remains in the warehouse. |
| **How do you find evidence?** | Declared code yields `POSSIBLE` candidate edges. Runtime telemetry (OpenLineage `COMPLETE` or query logs) yields `OBSERVED` verified edges. |
| **What happens if a pipeline fails?** | The static edge remains `POSSIBLE` or `REFUTED_FOR_RUN`. No green verified evidence is attached. |
| **Is the graph built in backend or frontend?** | Backend queries PostgreSQL and serves adjacency list via RLS. Frontend `catalog-graph.js` runs topological layering DAG algorithm. |
| **What if there are cycles in the SQL?** | `assignLayers()` is bounded by `nodes.length`, terminating safely without freezing the browser. |
| **Why bitemporality?** | Separates valid time (warehouse reality) from recorded time (ingestion time) for historical auditability and incident time-travel. |
| **How does asset removal work?** | Soft deletion (`removed_at = NOW()`). RLS policy hides it from catalog views, but historical lineage and raw events are preserved. |
| **What about ML and images?** | Metadata engines track S3 URIs, SHA-256 digests, and training runs, not raw pixels. Bitemporality prevents training data poisoning. |
| **Can Tenant A see Tenant B's data?** | No. PostgreSQL Row-Level Security (RLS) on all 43 tables evaluates `app.current_workspace_id`. Cross-tenant queries return 0 rows. |

---
*End of Master Context File. Use this authoritative specification to answer any inquiry regarding Kairos.*
