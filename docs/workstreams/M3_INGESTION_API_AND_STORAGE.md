# M3 — Ingestion API and Workspace Storage

**Owner:** Person 3 · **Timebox:** 2–3 hours · **Architecture:** [`../KAIROS_FINAL_ARCHITECTURE.md`](../KAIROS_FINAL_ARCHITECTURE.md)

## Goal

Implement the thin server-side ingestion orchestrator and authenticated preview/commit path for one supported `kairos.ingest.v1` file. Commit must be explicit, workspace-scoped, transactional, auditable, and idempotent. M3 owns the shared envelope and tells M1/M2/M5 about any contract change before merge.

## Inspect first

- `backend/app/main.py`, `backend/app/db.py`, auth dependency and routers.
- `backend/migrations/0001_core.sql` through `0003_personal_workspaces.sql` and migration README.
- Existing `/api/v1/catalog` read shape and import limitations in `frontend/ingestion.js`.

## Work

1. Define strict Pydantic request/response schemas for validate/preview and commit. Derive workspace and user only from the verified token/context; reject workspace IDs in client payloads.
2. Add bounded body/asset/relationship limits and validate endpoints/provenance before DB writes. Separate preview (no writes) from commit.
3. Persist one accepted metadata graph in a single transaction, with workspace-scoped identities, import/run record and an audit/provenance record. Add an idempotency key/unique constraint scoped to workspace and source content. Use existing canonical schema where possible; propose a numbered migration for missing structures.
4. Ensure all writes use the enforced `kairos_app` role and RLS path. Test forbidden/no context and cross-workspace reads/writes. Do not run production migration or disable RLS.
5. Return import ID and stable counts/warnings; re-read from `/catalog` or an equivalent workspace endpoint for dashboard readback. Send the fixture/API example to M5.

## Likely files

- `backend/app/api/routes/ingest.py` (new), schemas/services under `backend/app/`
- `backend/app/main.py`, numbered `backend/migrations/0004_*.sql` only if justified
- `tests/` focused API/storage tests

## Acceptance

- No bearer token → 401; invalid auth service/config → fail closed.
- Preview creates no catalog rows. Commit creates one workspace-scoped import. Same idempotency key repeated creates no duplicate.
- A second workspace cannot read/import the first workspace’s records.
- Invalid input returns actionable diagnostics, not successful zero-row import.
- If no configured PostgreSQL/Supabase test DB is available, record this as unverified; do not claim tenant isolation has passed.

