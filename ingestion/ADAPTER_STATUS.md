# Ingestion adapter inventory

This status describes code in this repository, not feature labels from the
Hatchable ZIP snapshot. “Preview” means browser-side validation/normalization;
it does not persist anything. Product imports must go through the authenticated
M3 API into the team's shared Supabase project.

| Input | Current implementation | Output semantics | Status / limit |
|---|---|---|---|
| SQL text + schema | `ingestion/sql/__init__.py` (`SQLGlotLineageProvider`) | Static dependency candidates only | **Implemented for the documented SQLGlot subset.** Unsupported/malformed SQL returns `UNSUPPORTED`; it is not proof of execution. See `ingestion/sql/SUPPORT_MATRIX.md`. |
| dbt `manifest.json` | `ingestion/dbt/manifest.py`, reachable through `ingestion/static_files.parse_static_file()` and `POST /api/v1/ingest/{preview,commit}` with `kind=dbt_manifest` | Declared dependencies between supported models, seeds, snapshots, sources, and exposures | **Adapter implemented and wired.** Does not prove a resource ran; dbt tests/metrics/macros are skipped. |
| Kairos metadata graph JSON | `ingestion/metadata_graph/__init__.py`, reachable through `POST /api/v1/ingest/{preview,commit}` with `kind=metadata_graph` | Explicitly supplied assets and declared relationships | **Parser/validator implemented by M1 and wired to persisted imports.** |
| Generic JSON records | `frontend/ingestion.js` | Browser preview transforms selected record arrays to metadata assets; no inferred lineage | **Preview only.** No backend adapter or persistent import. |
| File inventory JSON | `ingestion/static_files/inventory.py`, reachable through `ingestion/static_files.parse_static_file()` and `POST /api/v1/ingest/{preview,commit}` with `kind=file_inventory` | File assets plus path/size/hash metadata; no data-flow edges inferred | **Adapter implemented and wired.** |
| CSV headers | `ingestion/static_files/csv_headers.py`, reachable through `ingestion/static_files.parse_static_file()` and `POST /api/v1/ingest/{preview,commit}` with `kind=csv_headers` | One table asset with header names; data types stay unknown and data rows are ignored | **Header-only adapter implemented and wired.** The older CLI retains a separate unauthenticated push path and is not the supported product import flow. |
| OpenLineage events | `ingestion/openlineage/`, `POST /api/v1/ingest/openlineage` | Runtime job/run/dataset evidence, limited by event facets | **Parser and persisted ingest route implemented.** Producers authenticate with a session/API key, `KAIROS_OPENLINEAGE_WEBHOOK_SECRET`, or an `X-Kairos-Signature` HMAC over the raw body (`KAIROS_WEBHOOK_SIGNING_SECRET`). |

## Demo-safe M1 input

Use `ingestion.static_files.parse_static_file(kind, data, filename=...)` to
dispatch a metadata graph, dbt manifest, file inventory, or CSV header file into the shared v1
envelope. The same adapters back the authenticated import flow:
`POST /api/v1/ingest/preview` validates without writing, and
`POST /api/v1/ingest/commit` persists the normalized assets, declared edges and
provenance through the workspace-scoped API.

## Not implemented

MLflow runs, RAG/retrieval traces and column profilers have no adapter yet.
Source-system screenshots and generic JSON records remain preview-only.
