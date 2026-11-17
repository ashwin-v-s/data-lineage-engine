# Demo 3 — Local Folder and File Ingestion

**Presenter:** Anushka (M2) or Jatin (M1)  
**Duration:** 6–8 minutes  
**Status:** **100% COMPLETE & VERIFIED** (Updated 2026-11-17)  
**Prerequisite:** Backend running (`uvicorn backend.app.main:app --reload`), frontend built (`npm --prefix frontend run build`), signed in with a confirmed Supabase account.  
**Visual Artifacts:** [Local Folder Preview](../../.demo-sources/visual/demo3-local-preview.png) · [File Ingestion View](../../.demo-sources/visual/3-file-ingestion.png)

---

## Pre-flight verification checklist

Execute these commands before beginning the live demo:

```powershell
# 1. Confirm the authenticated enterprise demo fixture files exist in demo-authenticated-ingestion/
Get-ChildItem demo-authenticated-ingestion/ | Select-Object Name, Length

# Verified output:
#   customer_transactions_schema.csv (555 B, 10 columns)
#   dbt_production_manifest.json      (5,711 B, 8 assets, 8 edges)
#   enterprise_inventory.json         (946 B, 4 files cataloged)
#   enterprise_lineage_pipeline.sql   (3,010 B, 8 assets, 6 edges)
#   enterprise_metadata_graph.json    (16,489 B, 9 assets, 9 edges, column lineage)
#   README.md                         (5,973 B)

# 2. Run deterministic validation across all authenticated fixtures
$env:PYTHONPATH='.'; python scripts/demo/verify_authenticated_fixtures.py
# Verified output:
# [PASS] enterprise_metadata_graph.json: OK=True assets=9 edges=9
# [PASS] enterprise_lineage_pipeline.sql: OK=True assets=8 edges=6
# [PASS] dbt_production_manifest.json: OK=True assets=8 edges=8
# [PASS] customer_transactions_schema.csv: OK=True assets=1 columns=10
# [PASS] enterprise_inventory.json: OK=True assets=4
# All authenticated demo fixtures verified deterministically: 100% PASS.

# 3. Confirm ingestion & parser test suite
python -m pytest tests/test_ingestion_api.py tests/test_metadata_graph_adapter.py tests/test_sql_static_file_adapter.py tests/test_static_corpus.py tests/test_ingest_sql_dbt_route.py -q
# Verified output: 68 passed, 7 warnings

# 4. Optional: Pre-seed complete enterprise governance bindings (Glossary, Domains, Products, SLAs)
$env:PYTHONPATH='.'; python scripts/demo/seed_authenticated_demo.py
```

---

## Live Walkthrough Script

### Step 1 — Navigate to the Ingestion Console

1. From the Kairos authenticated dashboard, click **"Connect / import metadata"** or navigate to `/ingestion.html`.
2. Present the dual-pane ingestion interface:
   - **Left Panel: "Scan a local folder"** — uses the browser's native File System Access API (`window.showDirectoryPicker`).
   - **Right Panel: "Import metadata artifact"** — direct single-file preview & commit pipeline supporting 5 formats (`metadata_graph`, `dbt_manifest`, `sql_file`, `file_inventory`, `csv_headers`).
3. Show the **Metadata store status** at the bottom — actively queries `GET /api/v1/catalog` to show current workspace assets and recent raw source artifacts.

### Step 2 — Scan local demo folder via File System Access API

1. In the "Scan a local folder" panel, click **"Choose a folder"**.
2. The browser displays its native security prompt. Select `demo-authenticated-ingestion/` (or `docs/demo-fixtures/`) and grant read permission.
3. Show the scan results in the file tree:
   - Status: `Scanned 6 files in "demo-authenticated-ingestion"; 5 have supported extensions. Files are still on this computer. Nothing has been uploaded.`
   - The tree displays each file with its format badge and byte size (`enterprise_metadata_graph.json`, `enterprise_lineage_pipeline.sql`, `dbt_production_manifest.json`, `customer_transactions_schema.csv`, `enterprise_inventory.json`).
4. **Key examiner point:** *"Kairos can only read the specific folder selected by the user. It cannot silently scan the disk or traverse parent directories."*

### Step 3 — Client-side local preview (Zero Network Leakage)

1. Click on `enterprise_metadata_graph.json` in the scanned file tree. The item highlights with a blue focus border.
2. Click **"Preview selected file"**.
3. Inspect the local preview card:
   - Displays file name, detected format, byte size, and SHA-256 content digest.
   - The raw JSON content renders in a syntax-highlighted monospace viewer showing the 4-tier enterprise pipeline (`raw_enterprise`, `staging`, `analytics`, `executive`).
   - Status banner: *"Previewing enterprise_metadata_graph.json. Content remains local until you choose Ingest selected file."*
4. Open the DevTools Network tab to demonstrate to the examiner that **zero HTTP requests** were transmitted during preview.

### Step 4 — Ingest metadata graph via Two-Phase Preview & Commit

1. With `enterprise_metadata_graph.json` selected, click **"Ingest selected file"**.
2. Explain the two-phase protocol:
   - **Phase 1 (Validation):** `POST /api/v1/ingest/preview` sends the file content. The server parses the AST, validates constraints, and returns candidate asset (9) and edge (9) counts without writing to PostgreSQL.
   - **Phase 2 (Atomic Persistence):** `POST /api/v1/ingest/commit` sends the verified payload along with a client-generated UUID `idempotency_key`.
3. The server commits the records within a single database transaction, inserting:
   - Raw immutable event in `raw_event`.
   - Asset definitions in `dataset` (RLS-scoped to current workspace).
   - Declared relationships in `lineage_edge` (4 architectural tiers).
   - Evidence records in `evidence` with state `OBSERVED` for explicitly declared structure.
   - Run audit record in `import_run`.
4. **Idempotency proof:** Clicking commit a second time with the same idempotency key returns `replayed: true` and writes 0 duplicate rows.

### Step 5 — Scan & import folder inventory

1. Click **"Import folder inventory"**.
2. Show that all files from the selected directory are packaged into a file inventory envelope:
   - Paths, sizes, SHA-256 hashes, and directory membership relationships.
3. Status message: *"Imported folder inventory: 6 files from 'demo-authenticated-ingestion'. Inventory records paths and metadata; it does not infer data lineage."*
4. **Honesty point:** *"An inventory lists existing files. Kairos does NOT manufacture speculative data-flow edges between files just because they live in the same directory."*

### Step 6 — Ingest SQL static lineage (`enterprise_lineage_pipeline.sql`)

1. In the right-hand panel ("Import metadata artifact") or directly from the local folder tree:
2. Select `enterprise_lineage_pipeline.sql`.
3. Click **"Preview selected file"**:
   - Server runs SQLGlot AST analysis across 4 pipeline stages.
   - Extracts `CREATE TABLE staging.stg_orders_enriched AS SELECT ...`, `CREATE TABLE staging.stg_customer_360 AS SELECT ...`, `INSERT INTO analytics.fct_daily_revenue ...`, and `INSERT INTO executive.daily_revenue_kpi ...`.
   - Server preview card: `Assets: 8, Relationships: 6, Columns: 0`.
   - Status: `✓ Ready to commit to your isolated workspace`.
4. Click **"Confirm import"**.
5. Status: `Import saved. 8 assets and 6 declared relationships are now stored.`
6. **Examiner point:** *"SQL parsing produces STATIC candidate lineage. Kairos classifies this evidence as POSSIBLE, preserving the full SQL text in raw evidence. A plain SELECT query without an INSERT/CREATE target produces 0 lineage edges."*

### Step 7 — Catalog readback and evidence verification across UI

1. Click **"Refresh store status"** in the Metadata Store panel.
2. The asset count increments to reflect the newly persisted enterprise pipeline assets.
3. Click **"← Back to Kairos dashboard"** and inspect the connected UI:
   - **Lineage Explorer (`/lineage`):** Show the 4-tier directed DAG (`raw_enterprise` -> `staging` -> `analytics` -> `executive`). Click nodes to see upstream/downstream hop lists and blast radius.
   - **Edge Inspector:** Click any edge to open the drawer: inspect `evidence_type: STATIC_DEPENDENCY`, `provenance: dbt_model_ref`, valid time, recorded time, and the sanitized raw event link.
   - **Catalog & Schemas (`/assets`):** Inspect `customers`, `stg_orders_enriched`, and `fct_daily_revenue` schemas: show column data types, descriptions, and PII badges (`PII_SOURCE`, `PII_MASKED`).
   - **Glossary & PII (`/glossary`, `/pii`):** Inspect enterprise glossary terms (`GMV`, `Net Recognized Revenue`, `Customer LTV`, `PII`) and their linked dataset assets.
   - **Domains (`/domains`) & Data Products (`/products`):** Inspect `Executive Revenue Intelligence Product` and `Customer 360 Mart` with their active contracts and SLA clauses.
   - **Freshness & Quality (`/freshness`):** Inspect the healthy 24-hour freshness SLA on `analytics.fct_daily_revenue`.

---

## Evidence output log

```
==================================================================
1. Ingestion unit & route tests (pytest)
==================================================================
tests/test_ingestion_api.py::test_endpoints_require_authentication[preview] PASSED
tests/test_ingestion_api.py::test_endpoints_require_authentication[commit] PASSED
tests/test_ingestion_api.py::test_preview_returns_counts_digest_and_evidence_classification PASSED
tests/test_ingestion_api.py::test_preview_opens_no_database_connection PASSED
tests/test_ingestion_api.py::test_preview_warns_when_no_relationships_are_supplied PASSED
...
68 passed, 7 warnings in 3.97s

==================================================================
2. Deterministic fixture parsing verification
==================================================================
metadata_graph.json : OK=True assets=2 edges=1
demo_revenue.sql    : OK=True assets=4 edges=2
manifest.json       : OK=True assets=3 edges=2
demo_orders.csv     : OK=True assets=1 edges=0

==================================================================
3. Live database acceptance (PostgreSQL 17.6)
==================================================================
POST /api/v1/ingest/preview  -> 200 OK (assets=2, relationships=1, writes=0)
POST /api/v1/ingest/commit   -> 200 OK (persisted_assets=2, import_id=<uuid>)
POST /api/v1/ingest/commit   -> 200 OK (replayed=true, duplicate_writes=0)
GET  /api/v1/catalog         -> 200 OK (returned imported assets under workspace RLS)
```

---

## Supported artifact formats & evidence classification

| Format | Selector value | Content type | Extracted Assets | Extracted Relationships | Evidence Classification |
|---|---|---|---|---|---|
| **Kairos Metadata Graph** | `metadata_graph` | JSON | Explicitly declared datasets/jobs | Explicitly declared edges | `OBSERVED` structure / declared provenance |
| **SQL Static File** | `sql_file` | SQL text | DDL/DML targets and source tables | `CREATE ... AS SELECT`, `INSERT ... SELECT` | `POSSIBLE` static candidate (not runtime execution) |
| **dbt Manifest** | `dbt_manifest` | JSON | Models, sources, seeds | `depends_on.nodes` references | Declared DAG dependency |
| **File Inventory** | `file_inventory` | JSON | Files and directory nodes | Directory hierarchy membership | Directory containment only (no data flow) |
| **CSV Headers** | `csv_headers` | CSV text | Table asset from filename | Column schemas from header row | Schema metadata only; types `UNKNOWN` |

---

## Viva Defense Q&A: Local Folder & File Ingestion

| Question | Answer & Code Reference |
|---|---|
| **Why does Demo 3 offer both folder scan and single-file upload?** | The browser's File System Access API (`showDirectoryPicker`) is only supported in Chromium-based browsers (Chrome, Edge). Single-file upload via standard `<input type="file">` provides universal cross-browser fallback (Firefox, Safari). (`frontend/ingestion.js:5-30`) |
| **How does Kairos guarantee that `/api/v1/ingest/preview` writes nothing to PostgreSQL?** | `backend/app/api/routes/ingest.py:preview_import` invokes the pure static adapter parser in memory. The function never acquires a database connection from `get_conn()`, proven by `tests/test_ingestion_api.py::test_preview_opens_no_database_connection`. |
| **What prevents duplicate asset insertion on network retries?** | The client generates a random UUID `idempotency_key` per upload session. `backend/app/api/routes/ingest.py:commit_import` checks for an existing `import_run` with that key. If found, it immediately returns `replayed: true` with the original summary without writing rows. |
| **Does parsing a SQL file prove data flowed between tables?** | **No.** SQL parsing is purely *static evidence*. It proves only that the SQL statement declared a dependency in its code. Kairos labels this evidence `POSSIBLE`. It requires runtime execution evidence (e.g., OpenLineage in Demo 7) to elevate an edge to `OBSERVED`. |
| **Where is the original uploaded file preserved?** | The raw content is hashed (SHA-256) and stored in `public.raw_event` with `event_type = 'STATIC_FILE_IMPORT'`. An immutable Postgres trigger (`raw_event_immutable`) forbids any UPDATE or DELETE on raw event records. (`backend/migrations/0001_core.sql`) |
