-- PROPOSAL ONLY: NOT APPLIED TO THE SHARED SUPABASE PROJECT.
-- Requires M3 contract-owner review before deployment.
-- Migration 0006: workspace-scoped private GitHub App connections.
-- Apply after 0005_personalization.sql.
-- Only an explicit connect/callback action writes this table, and the stored
-- installation token is always the AES-256-GCM envelope produced by
-- backend/app/services/token_crypto.py -- never plaintext.

CREATE TABLE github_connection (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL
        DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid
        REFERENCES kairos_workspace(id),
    user_id UUID NOT NULL,
    installation_id BIGINT NOT NULL,
    account_login TEXT,
    account_type TEXT,
    token_ciphertext BYTEA NOT NULL,
    token_key_version SMALLINT NOT NULL DEFAULT 1
        CHECK (token_key_version BETWEEN 0 AND 255),
    token_expires_at TIMESTAMPTZ,
    scopes TEXT,
    permissions JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(permissions) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT github_connection_workspace_installation_key
        UNIQUE (workspace_id, installation_id)
);

CREATE INDEX idx_github_connection_workspace
    ON github_connection (workspace_id, created_at DESC);

ALTER TABLE github_connection ENABLE ROW LEVEL SECURITY;
ALTER TABLE github_connection FORCE ROW LEVEL SECURITY;
CREATE POLICY kairos_workspace_isolation ON github_connection
    USING (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid)
    WITH CHECK (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid);

-- Credentials are workspace-private. Only the restricted API login may touch
-- them; they are never exposed through the generated PostgREST API.
REVOKE ALL ON TABLE github_connection FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE github_connection TO kairos_app;

COMMENT ON TABLE github_connection IS
    'Workspace-scoped private GitHub App connections. Holds only the encrypted installation token.';
COMMENT ON COLUMN github_connection.token_ciphertext IS
    'AES-256-GCM envelope from token_crypto.encrypt_token; must never hold plaintext.';
COMMENT ON COLUMN github_connection.token_key_version IS
    'Key version of token_ciphertext, used to drive rotation via token_crypto.';
