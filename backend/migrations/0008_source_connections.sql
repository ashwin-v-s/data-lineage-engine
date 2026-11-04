-- NOT VERIFIED APPLIED: source_connection not confirmed in live DB.
-- Run `python scripts/db/verify_applied.py` before marking Applied.
-- Migration 0008: workspace-scoped live PostgreSQL source connections.
-- Apply after 0007_membership_roles.sql.
-- Adds source_connection: a private, workspace-scoped connector to an external
-- PostgreSQL database. The connection configuration (including the password)
-- is only ever stored as the AES-256-GCM envelope produced by
-- backend/app/services/token_crypto.py -- never plaintext. Only the connector
-- lifecycle state and safe metadata are ever exposed to the API.
-- APPLIED to the shared Supabase project; the 'source_connection' table exists live.

CREATE TABLE source_connection (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL
        DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid
        REFERENCES kairos_workspace(id),
    created_by UUID NOT NULL,
    name TEXT NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 128),
    source_kind TEXT NOT NULL CHECK (source_kind IN ('postgresql')),
    config_ciphertext BYTEA NOT NULL,
    config_key_version SMALLINT NOT NULL DEFAULT 1
        CHECK (config_key_version BETWEEN 0 AND 255),
    lifecycle_state TEXT NOT NULL DEFAULT 'CONFIGURED'
        CHECK (lifecycle_state IN ('CONFIGURED', 'VERIFIED', 'ERROR', 'REVOKED')),
    last_checked_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT source_connection_workspace_name_key UNIQUE (workspace_id, name)
);

CREATE INDEX idx_source_connection_workspace
    ON source_connection (workspace_id, created_at DESC);

ALTER TABLE source_connection ENABLE ROW LEVEL SECURITY;
ALTER TABLE source_connection FORCE ROW LEVEL SECURITY;
CREATE POLICY kairos_workspace_isolation ON source_connection
    USING (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid)
    WITH CHECK (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid);

-- Source credentials are workspace-private. Only the restricted API login may
-- touch them; they are never exposed through the generated PostgREST API.
DO $$
DECLARE r TEXT;
BEGIN
    FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
            EXECUTE format('REVOKE ALL ON TABLE public.%I FROM %I', 'source_connection', r);
        END IF;
    END LOOP;
END $$;
REVOKE ALL ON TABLE source_connection FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE source_connection TO kairos_app;

COMMENT ON TABLE source_connection IS
    'Workspace-scoped live PostgreSQL source connectors. Holds only the encrypted connection configuration.';
COMMENT ON COLUMN source_connection.config_ciphertext IS
    'AES-256-GCM envelope from token_crypto.encrypt_token; must never hold plaintext.';
COMMENT ON COLUMN source_connection.config_key_version IS
    'Key version of config_ciphertext, used to drive rotation via token_crypto.';
COMMENT ON COLUMN source_connection.lifecycle_state IS
    'Connector lifecycle state machine: CONFIGURED -> VERIFIED -> ERROR -> REVOKED.';


