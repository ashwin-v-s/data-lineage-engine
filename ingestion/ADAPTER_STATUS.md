# Ingestion adapter inventory

This status describes code in this repository, not feature labels from the
Hatchable ZIP snapshot. “Preview” means browser-side validation/normalization;
it does not persist anything. Product imports must go through the authenticated
M3 API into the team's shared Supabase project.

| Input | Current implementation | Output semantics | Status / limit |
|---|---|---|---|
| SQL text + schema | `ingestion/sql/__init__.py` (`SQLGlotLineageProvider`) | Static dependency candidates only | **Implemented for the documented SQLGlot subset.** Unsupported/malformed SQL returns `UNSUPPORTED`; it is not proof of execution. See `ingestion/sql/SUPPORT_MATRIX.md`. |
| dbt `manifest.json` | `ingestion/dbt/manifest.py`, reachable through `ingestion/static_files.parse_static_file()` | Declared dependencies between supported models, seeds, snapshots, sources, and exposures | **Pure Python adapter implemented.** Does not prove a resource ran; dbt tests/metrics/macros are skipped. No storage/API wiring; M3 owns that. |
| Kairos metadata graph JSON | `ingestion/metadata_graph/__init__.py` | Explicitly supplied assets and declared relationships | **Pure Python parser/validator implemented by M1.** No storage/API wiring yet; M3 owns that. |
| Generic JSON records | `frontend/ingestion.js` | Browser preview transforms selected record arrays to metadata assets; no inferred lineage | **Preview only.** No backend adapter or persistent import. |
| File inventory JSON | `ingestion/static_files/inventory.py`, reachable through `ingestion/static_files.parse_static_file()` | File assets plus path/size/hash metadata; no data-flow edges inferred | **Pure Python adapter implemented.** No storage/API wiring; M3 owns that. |
| CSV headers | `ingestion/static_files/csv_headers.py`, reachable through `ingestion/static_files.parse_static_file()` | One table asset with header names; data types stay unknown and data rows are ignored | **Pure Python header-only adapter implemented.** The older CLI retains a separate unauthenticated push path and is not the supported product import flow. |
| OpenLineage events | `ingestion/openlineage/` | Runtime job/run/dataset evidence, limited by event facets | **M2-owned parser exists;** see M2 workstream for semantic coverage and test status. |

## Demo-safe M1 input

Use `ingestion.static_files.parse_static_file(kind, data, filename=...)` to
dispatch a metadata graph, dbt manifest, file inventory, or CSV header file into the shared v1
envelope. These adapters implement the extract/normalize/validate stage used
by connector-style pipelines; they do not persist data. Authenticated
preview/commit and Supabase persistence remain M3 work.
