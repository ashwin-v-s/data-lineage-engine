# Ingestion adapter inventory

This status describes code in this repository, not feature labels from the
Hatchable ZIP snapshot. “Preview” means browser-side validation/normalization;
it does not persist anything. Product imports must go through the authenticated
M3 API into the team's shared Supabase project.

| Input | Current implementation | Output semantics | Status / limit |
|---|---|---|---|
| SQL text + schema | `ingestion/sql/__init__.py` (`SQLGlotLineageProvider`) | Static dependency candidates only | **Implemented for the documented SQLGlot subset.** Unsupported/malformed SQL returns `UNSUPPORTED`; it is not proof of execution. See `ingestion/sql/SUPPORT_MATRIX.md`. |
| dbt `manifest.json` | `frontend/ingestion.js` preview counters; `ingestion/dbt/README.md` only | Intended declared dependency metadata | **Python/server adapter absent.** Browser preview does not normalize or store the manifest. |
| Kairos metadata graph JSON | `ingestion/metadata_graph/__init__.py` | Explicitly supplied assets and declared relationships | **Pure Python parser/validator implemented by M1.** No storage/API wiring yet; M3 owns that. |
| Generic JSON records | `frontend/ingestion.js` | Browser preview transforms selected record arrays to metadata assets; no inferred lineage | **Preview only.** No backend adapter or persistent import. |
| File inventory JSON | `frontend/ingestion.js` | Browser preview and file/directory membership graph; membership is not data lineage | **Preview only.** Python/shared API adapter absent. |
| CSV files | `ingestion/cli/kairos_ingest.py` | Legacy local header scan to column names/types | **Partial legacy CLI.** Not a unified or authenticated Supabase import path; do not present its push method as working import. |
| OpenLineage events | `ingestion/openlineage/` | Runtime job/run/dataset evidence, limited by event facets | **M2-owned parser exists;** see M2 workstream for semantic coverage and test status. |

## Demo-safe M1 input

Use `tests/fixtures/ingestion/metadata_graph/valid.json` as the shared v1
contract fixture. The M1 parser produces deterministic normalized JSON and
structured diagnostics. Preview/commit endpoints and Supabase persistence are
still M3 work; this adapter alone is not an end-to-end import.
