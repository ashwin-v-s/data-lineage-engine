# Demo 3 — Local Folder Ingestion

**Presenter:** Anushka (M2) or Jatin (M1)
**Duration:** 6–8 minutes
**Prerequisite:** Backend running, frontend built, signed in with a confirmed Supabase account. The demo fixtures in `docs/demo-fixtures/` must be present.

---

## Pre-flight checklist

```powershell
# 1. Confirm the demo fixture files exist
Get-ChildItem docs/demo-fixtures/ | Select-Object Name, Length

# Expected:
#   demo_orders.csv        (small CSV with header row)
#   demo_revenue.sql       (CREATE TABLE AS SELECT + INSERT SELECT)
#   manifest.json          (dbt manifest: 1 model, 2 sources)
#   metadata_graph.json    (kairos.ingest.v1: 2 assets, 1 relationship)
#   README.md

# 2. Confirm parsers work on these fixtures
python -m pytest tests/test_ingestion_api.py tests/test_metadata_graph_adapter.py tests/test_sql_static_file_adapter.py tests/test_static_corpus.py -q
# Expected: 41+ passed

# 3. Confirm backend is running and authenticated
curl -H "Authorization: Bearer <your-token>" http://localhost:8000/api/v1/catalog
# Expected: 200 with catalog data (possibly empty)
```

---

## Walkthrough

### Step 1 — Navigate to the ingestion page

1. From the Kairos dashboard, click **"Connect / import metadata"** or **"Add / import source"**.
2. This navigates to `/ingestion.html`.
3. Show the page has two panels:
   - **Left: "Scan a local folder"** — uses the browser's File System Access API.
   - **Right: "Import metadata artifact"** — direct file upload with format selector.
4. Show the **Metadata store** section at the bottom — it queries `GET /api/v1/catalog` for persisted records.

### Step 2 — Choose the demo fixtures folder

1. Click **"Choose a folder"** in the "Scan a local folder" panel.
2. In the browser's folder picker, navigate to and select `docs/demo-fixtures/`.
3. Grant read permission when the browser prompts.
4. Show the scan results:
   - Status: `Scanned 5 files in "demo-fixtures"; 4 have supported extensions. Files are still on this computer. Nothing has been uploaded.`
   - The file tree displays each file with its format and size.
   - **Key point:** "Kairos can only read the folder you select. It does not scan the whole computer."

### Step 3 — Preview a file locally

1. Click on `metadata_graph.json` in the file list (it becomes highlighted with a blue border).
2. Click **"Preview selected file"**.
3. Show the local preview panel:
   - File name, format, size, and SHA-256 hash.
   - The raw JSON content rendered in a monospace pre block.
   - Status: "Previewing metadata_graph.json. Content remains local until you choose Ingest selected file."
4. **Key point:** "This preview happened entirely in the browser. No data was sent to the server."

### Step 4 — Ingest the metadata graph file

1. With `metadata_graph.json` still selected, click **"Ingest selected file"**.
2. Show the progress:
   - Status updates: "Preview found 2 asset(s). Saving selected file evidence…"
   - On success: "Imported metadata_graph.json into this workspace (2 file assets). The original content is retained in the import's raw evidence."
3. Show what happened under the hood:
   - `POST /api/v1/ingest/preview` — validated the file server-side, found 2 assets and 1 relationship.
   - `POST /api/v1/ingest/commit` — persisted the assets with an idempotency key.
4. **Key point:** "The import used the authenticated API. The idempotency key means replaying the same import is safe and returns `replayed: true`."

### Step 5 — Import the folder inventory

1. Click **"Import folder inventory"**.
2. Show: all 5 files from the selected folder are sent as an inventory record.
3. Status: "Imported folder inventory: 5 files from 'demo-fixtures'. Inventory records paths and metadata; it does not infer data lineage."
4. **Key point:** "A folder inventory records file paths, sizes, modification times, and hashes. It does NOT pretend to infer which file produced which."

### Step 6 — Import via the artifact upload panel

1. In the **"Import metadata artifact"** panel on the right:
2. Set **Artifact format** to "SQL file (static lineage)".
3. Click **Browse** and select `docs/demo-fixtures/demo_revenue.sql`.
4. Click **"Preview selected file"**.
5. Show the server preview:
   - "Server validation passed"
   - Assets: 4, Relationships: 2, Columns: 0
   - "✓ Ready to commit to your isolated workspace"
6. Click **"Confirm import"**.
7. Show: "Import saved. 4 assets and 2 declared relationships are now stored."
8. **Key point:** "The SQL parser extracted `CREATE TABLE ... AS SELECT` and `INSERT ... SELECT` targets and source candidates. A plain `SELECT` does NOT invent a target or lineage edge. This is static evidence, not proof that the query executed."

### Step 7 — Catalog readback

1. Scroll down to the **Metadata store** section.
2. Click **"Refresh store status"** (or it auto-refreshes after import).
3. Show the catalog now contains the imported assets.
4. Navigate back to the **Kairos dashboard** (click "← Back to Kairos dashboard").
5. Show the dashboard overview now displays the ingested assets in the catalog.
6. Click on an asset to see its detail page — show the metadata, source system, and import evidence.

### Step 8 — Evidence trail

1. On an imported asset's detail page, show:
   - The raw import evidence preserved in the import run.
   - The idempotency key linking this import.
   - The `source_kind: upload` and `source_ref` fields.
2. In the lineage view, show the declared edges from the SQL import.
3. **Key point:** "Every imported artifact is traceable back to the specific file, adapter, and import run that produced it."

---

## Evidence commands (paste into your demo PR)

```powershell
# Parser unit tests
python -m pytest tests/test_ingestion_api.py tests/test_metadata_graph_adapter.py tests/test_sql_static_file_adapter.py tests/test_static_corpus.py -q

# Specific fixture validation
python -c "
from ingestion.static_files import parse_static_file
import json
with open('docs/demo-fixtures/metadata_graph.json') as f:
    result = parse_static_file('metadata_graph', json.load(f), filename='metadata_graph.json')
print(f'OK={result.ok} assets={len(result.payload[\"assets\"])} edges={len(result.payload[\"relationships\"])}')
"
# Expected: OK=True assets=2 edges=1

python -c "
from ingestion.static_files import parse_static_file
with open('docs/demo-fixtures/demo_revenue.sql') as f:
    result = parse_static_file('sql_file', f.read(), filename='demo_revenue.sql')
print(f'OK={result.ok} assets={len(result.payload[\"assets\"])} edges={len(result.payload[\"relationships\"])}')
"
# Expected: OK=True assets=4 edges=2
```

---

## What this demo does NOT prove

- **No runtime lineage.** SQL parsing is static evidence — it does NOT prove the query executed or that data actually flowed.
- **No column-level lineage.** The SQL adapter extracts table-level candidates; column-level mapping is incomplete.
- **Directory access is user-initiated.** The browser's `showDirectoryPicker` requires explicit user consent. Kairos cannot silently traverse the filesystem.
- **File content is not auto-ingested.** Scanning a folder lists file metadata only. Only files the user explicitly selects and ingests are sent to the server.
- **Browser compatibility.** `showDirectoryPicker` requires Chrome/Edge. Firefox users must use the single-file upload panel.

---

## Supported artifact formats

| Format | Selector value | Content type | What it imports |
|---|---|---|---|
| Kairos metadata graph | `metadata_graph` | JSON | Explicit assets and declared relationships |
| dbt manifest | `dbt_manifest` | JSON | Models, sources, declared dependencies |
| SQL file | `sql_file` | Plain text | Static lineage candidates from DDL/DML |
| File inventory | `file_inventory` | JSON | Paths, sizes, hashes, directory membership |
| CSV headers | `csv_headers` | Plain text | Header row metadata; sample data rows ignored |
