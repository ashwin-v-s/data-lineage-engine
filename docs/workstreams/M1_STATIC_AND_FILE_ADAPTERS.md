# M1 — Static and File Adapters

**Owner:** Person 1 · **Timebox:** 2–3 hours · **Architecture:** [`../KAIROS_FINAL_ARCHITECTURE.md`](../KAIROS_FINAL_ARCHITECTURE.md)

## Goal

Produce typed, deterministic metadata from user-supplied files without writing to PostgreSQL. Adapters return the shared `kairos.ingest.v1` concepts: assets, relationship candidates, evidence/provenance, and diagnostics. The orchestrator/storage owner (M3) controls final contract/API changes.

## Inspect first

- `ingestion/sql/` and its existing fixtures/tests.
- `ingestion/dbt/` (README and any implementation; do not assume a README means an adapter exists).
- Existing JSON normalization/preview in `frontend/ingestion.js` and the Hatchable v306 ZIP reference.
- `contracts/` for existing asset/evidence types.

## Work

1. Inventory what actually parses today: SQL parser subset, dbt manifest support, generic metadata graph JSON, file inventory/CSV preview. Label each implemented, partial, or absent.
2. Choose one bounded file adapter for the demo fixture. Validate required keys, types, identifiers, relationship endpoints, file size/count, and unknown version. Preserve source filename/revision and content hash.
3. Add fixtures: a minimal valid graph with two assets and one explicitly declared edge; invalid endpoint; unknown version; oversized/unsupported example. Make output deterministic and diagnostics actionable.
4. For SQL/dbt, retain static/declared classification. Unsupported SQL or malformed dbt metadata produces diagnostics; do not manufacture runtime events.
5. Share the fixture and expected adapter output with M3/M5. Do not edit their API, DB migration, React app, or research truth provider.

## Likely files

- `ingestion/metadata_graph/` (create if absent), `ingestion/dbt/`, `ingestion/sql/`
- `tests/fixtures/ingestion/`, focused adapter tests
- Propose a contract change to M3 before touching a shared contract module.

## Acceptance

- Same valid input yields identical normalized output.
- Explicit links are distinguished from inferred static SQL candidates.
- Invalid/unsupported content has diagnostics and cannot become a silent empty import.
- No network access, SQL execution, DB writes, credentials, or ground-truth imports.
