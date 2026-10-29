-- PROPOSAL ONLY: NOT APPLIED TO THE SHARED SUPABASE PROJECT.
-- Requires M3 contract-owner review before deployment.
-- Migration 0004: workspace-scoped import provenance and idempotency records.
-- Apply after 0003_personal_workspaces.sql.
-- The preview path must not write this table; successful explicit commits do.

CREATE TABLE import_run (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid
        REFERENCES kairos_workspace(id),
    actor_user_id UUID NOT NULL,
    idempotency_key TEXT NOT NULL
        CHECK (length(btrim(idempotency_key)) BETWEEN 1 AND 256),
    source_kind TEXT NOT NULL
        CHECK (source_kind IN ('upload', 'github', 'database', 'cli')),
    source_ref TEXT,
    content_sha256 TEXT NOT NULL
        CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    contract_version TEXT NOT NULL
        CHECK (contract_version = 'kairos.ingest.v1'),
    adapter_name TEXT NOT NULL,
    adapter_version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'COMMITTED'
        CHECK (status IN ('COMMITTED', 'COMMITTED_WITH_WARNINGS')),
    result_summary JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(result_summary) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT import_run_workspace_idempotency_key UNIQUE (workspace_id, idempotency_key)
);

CREATE INDEX idx_import_run_workspace_created
    ON import_run (workspace_id, created_at DESC);

ALTER TABLE import_run ENABLE ROW LEVEL SECURITY;
ALTER TABLE import_run FORCE ROW LEVEL SECURITY;
CREATE POLICY kairos_workspace_isolation ON import_run
    USING (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid)
    WITH CHECK (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid);

REVOKE ALL ON TABLE import_run FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE import_run TO kairos_app;

COMMENT ON TABLE import_run IS
    'Committed ingestion provenance; preview is read-only and is not recorded here.';
COMMENT ON COLUMN import_run.idempotency_key IS
    'Unique per workspace. On a retry, the API must confirm the source/content matches the stored record.';
COMMENT ON COLUMN import_run.result_summary IS
    'Counts and safe diagnostics returned by the commit; never store secrets or raw credentials.';
