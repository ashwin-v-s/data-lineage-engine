-- Migration 0010: Widen source_connection lifecycle + add schedule / sync history.
-- Apply after 0009_governance.sql.
-- Owner: M2 (Anushka).
--
-- What this fixes
-- ───────────────
-- 0008 allowed only 4 lifecycle states (CONFIGURED, VERIFIED, ERROR, REVOKED).
-- Architecture v2 §5.4 requires 12 states to represent the full connector
-- journey. This migration:
--   1. Drops the old 4-state CHECK on lifecycle_state.
--   2. Re-adds the CHECK with all 12 states.
--   3. Adds schedule / incremental-sync columns required by the health rollup
--      (/sources/health 12-field diagnostic) and the scheduler proposal.
--   4. Adds sync_job table to track per-source sync runs (replaces the missing
--      sync history that the API was returning empty arrays for).
--
-- 12-state lifecycle (Architecture v2 §5.4)
-- ──────────────────────────────────────────
-- CONFIGURED          Credentials stored, not yet tested.
-- AUTHENTICATED       Credential test passed (connect + auth only).
-- REACHABLE           Network reachability confirmed.
-- AUTHORIZED          Grants confirmed (read-only role check passed).
-- DISCOVERY_PENDING   Scope selected, discovery queued.
-- DISCOVERY_RUNNING   Discovery job executing.
-- DISCOVERY_COMPLETE  Discovery finished; counts available for review.
-- NORMALIZED          Schema mapped to Kairos canonical identity.
-- PERSISTED           Evidence rows written to Supabase.
-- VERIFIED            Full pipeline confirmed end-to-end.
-- ERROR               Any step failed; last_error carries the reason.
-- REVOKED             Connection disabled; evidence kept as historical record.
-- CREDENTIALS_EXPIRED Credential rotation required before re-use.
-- SYNC_FAILED         A scheduled sync failed after a previously VERIFIED state.
-- STALE               Last successful sync older than the configured threshold.
-- REFRESH_IN_PROGRESS A manual or scheduled refresh is currently running.
--
-- NOT IMPLEMENTED: APPLIED to shared Supabase project.
-- Run `python scripts/db/verify_applied.py` after applying and update this header.

BEGIN;

-- ────────────────────────────────────────────────────────────────────────────
-- 1. Drop the old 4-state CHECK and add the full 16-state CHECK
-- ────────────────────────────────────────────────────────────────────────────
ALTER TABLE source_connection
    DROP CONSTRAINT IF EXISTS source_connection_lifecycle_state_check;

ALTER TABLE source_connection
    ADD CONSTRAINT source_connection_lifecycle_state_check
        CHECK (lifecycle_state IN (
            'CONFIGURED',
            'AUTHENTICATED',
            'REACHABLE',
            'AUTHORIZED',
            'DISCOVERY_PENDING',
            'DISCOVERY_RUNNING',
            'DISCOVERY_COMPLETE',
            'NORMALIZED',
            'PERSISTED',
            'VERIFIED',
            'ERROR',
            'REVOKED',
            'CREDENTIALS_EXPIRED',
            'SYNC_FAILED',
            'STALE',
            'REFRESH_IN_PROGRESS'
        ));

-- ────────────────────────────────────────────────────────────────────────────
-- 2. Add schedule / sync columns to source_connection
--    Required by the /sources/health 12-field diagnostic and the scheduler.
-- ────────────────────────────────────────────────────────────────────────────

-- When the next scheduled sync should fire (NULL = no schedule configured).
ALTER TABLE source_connection
    ADD COLUMN IF NOT EXISTS next_sync_at TIMESTAMPTZ;

-- Cron expression for scheduled syncs, e.g. '0 */6 * * *' (every 6 hours).
-- NULL means the source is manual-only.
ALTER TABLE source_connection
    ADD COLUMN IF NOT EXISTS sync_schedule TEXT;

-- Cursor value for incremental syncs: updated_at watermark, commit SHA, event
-- id, etc.  NULL means the next sync is a full snapshot.
ALTER TABLE source_connection
    ADD COLUMN IF NOT EXISTS sync_cursor TEXT;

-- Snapshot hash of the last full discovery result.  Changes signal structural
-- drift in the source schema.
ALTER TABLE source_connection
    ADD COLUMN IF NOT EXISTS source_snapshot_hash TEXT;

-- Counts from the last completed sync run (populated by the sync worker).
ALTER TABLE source_connection
    ADD COLUMN IF NOT EXISTS last_assets_discovered INTEGER;

ALTER TABLE source_connection
    ADD COLUMN IF NOT EXISTS last_assets_created INTEGER;

ALTER TABLE source_connection
    ADD COLUMN IF NOT EXISTS last_assets_updated INTEGER;

ALTER TABLE source_connection
    ADD COLUMN IF NOT EXISTS last_assets_unchanged INTEGER;

ALTER TABLE source_connection
    ADD COLUMN IF NOT EXISTS last_assets_deleted INTEGER;

ALTER TABLE source_connection
    ADD COLUMN IF NOT EXISTS last_assets_failed INTEGER;

-- Permission gaps: list of schema/table combinations that were discovered but
-- could not be read due to missing grants.  Stored as a JSONB array of strings.
-- Empty array [] means full access; NULL means not yet evaluated.
ALTER TABLE source_connection
    ADD COLUMN IF NOT EXISTS permission_gaps JSONB;

-- Timestamp of the last *successful* sync (not the last attempted sync).
ALTER TABLE source_connection
    ADD COLUMN IF NOT EXISTS last_successful_sync_at TIMESTAMPTZ;

-- Duration of the last sync in milliseconds.
ALTER TABLE source_connection
    ADD COLUMN IF NOT EXISTS last_sync_duration_ms INTEGER;

COMMENT ON COLUMN source_connection.lifecycle_state IS
    'Connector lifecycle (16 states): CONFIGURED → AUTHENTICATED → REACHABLE → '
    'AUTHORIZED → DISCOVERY_PENDING → DISCOVERY_RUNNING → DISCOVERY_COMPLETE → '
    'NORMALIZED → PERSISTED → VERIFIED. Side-states: ERROR, REVOKED, '
    'CREDENTIALS_EXPIRED, SYNC_FAILED, STALE, REFRESH_IN_PROGRESS.';

COMMENT ON COLUMN source_connection.next_sync_at IS
    'When the next scheduled sync should fire. NULL means manual-only.';

COMMENT ON COLUMN source_connection.sync_schedule IS
    'Cron expression for scheduled syncs (e.g. ''0 */6 * * *''). NULL = manual only.';

COMMENT ON COLUMN source_connection.sync_cursor IS
    'Watermark for incremental syncs. NULL triggers a full snapshot.';

COMMENT ON COLUMN source_connection.permission_gaps IS
    'JSONB array of objects {schema, table, reason} for assets discovered but '
    'unreadable. Empty = full access; NULL = not yet evaluated.';

COMMENT ON COLUMN source_connection.source_snapshot_hash IS
    'Hash of the last full discovery result. Drift from a previous hash '
    'means the source schema has changed since the last sync.';

-- ────────────────────────────────────────────────────────────────────────────
-- 3. sync_job: per-source sync run history
--    Satisfies /sources/{id}/runs and the "last N syncs" health rollup.
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sync_job (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL
        DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid
        REFERENCES kairos_workspace(id),
    source_connection_id UUID NOT NULL REFERENCES source_connection(id),
    -- Sync mode: one of the five defined in Architecture v2 §5.5
    sync_mode TEXT NOT NULL DEFAULT 'manual'
        CHECK (sync_mode IN (
            'full_snapshot',
            'incremental',
            'event_driven',
            'scheduled',
            'manual'
        )),
    -- Terminal states only; running state tracked in source_connection.lifecycle_state
    status TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    duration_ms INTEGER GENERATED ALWAYS AS (
        CASE
            WHEN finished_at IS NOT NULL
            THEN EXTRACT(EPOCH FROM (finished_at - started_at))::INTEGER * 1000
            ELSE NULL
        END
    ) STORED,
    -- Counts
    assets_discovered INTEGER,
    assets_created INTEGER,
    assets_updated INTEGER,
    assets_unchanged INTEGER,
    assets_deleted INTEGER,
    assets_failed INTEGER,
    -- Cursors
    cursor_before TEXT,     -- cursor value at start of this sync
    cursor_after TEXT,      -- cursor value at end (used for next incremental sync)
    snapshot_hash TEXT,     -- hash of the full discovered schema (full_snapshot only)
    -- Error details
    error_message TEXT,
    -- Metadata: any extra context (e.g. triggered_by, scheduler_job_id)
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(metadata) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sync_job_source
    ON sync_job (workspace_id, source_connection_id, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_sync_job_status
    ON sync_job (workspace_id, status, started_at DESC);

-- RLS: sync jobs are workspace-private, same policy pattern as governance tables.
ALTER TABLE sync_job ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_job FORCE ROW LEVEL SECURITY;

CREATE POLICY kairos_workspace_isolation ON sync_job
    USING (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid)
    WITH CHECK (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid);

-- Revoke from Supabase auto-generated roles; only kairos_app may touch this.
DO $$
DECLARE r TEXT;
BEGIN
    FOREACH r IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
            EXECUTE format(
                'REVOKE ALL ON TABLE public.%I FROM %I',
                'sync_job', r
            );
        END IF;
    END LOOP;
END $$;

REVOKE ALL ON TABLE sync_job FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE sync_job TO kairos_app;

COMMENT ON TABLE sync_job IS
    'Append-only sync run history per source connection. One row per sync '
    'attempt; status transitions from running → completed/failed/cancelled.';

COMMENT ON COLUMN sync_job.sync_mode IS
    'One of the five sync modes from Architecture v2 §5.5: full_snapshot, '
    'incremental, event_driven, scheduled, manual.';

COMMENT ON COLUMN sync_job.duration_ms IS
    'Computed from started_at and finished_at. NULL while still running.';

COMMIT;
