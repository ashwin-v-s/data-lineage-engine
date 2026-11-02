-- Migration 0007: workspace membership and invitations.
-- Apply after 0006_github_connections.sql.
-- Adds workspace_member (a user's role inside one workspace) and
-- workspace_invite (a pending email invitation that cannot grant ownership).
-- Membership is the source of truth for a user's role in a workspace; the role
-- is never read from the JWT.
-- APPLIED to the shared Supabase project; the 'workspace_member' and
-- 'workspace_invite' tables exist live.

CREATE TABLE workspace_member (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL
        DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid
        REFERENCES kairos_workspace(id),
    user_id UUID NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('owner', 'admin', 'editor', 'viewer')),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'invited', 'removed')),
    invited_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT workspace_member_workspace_user_key UNIQUE (workspace_id, user_id)
);

CREATE INDEX idx_workspace_member_workspace
    ON workspace_member (workspace_id, created_at DESC);

CREATE TABLE workspace_invite (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL
        DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid
        REFERENCES kairos_workspace(id),
    email TEXT NOT NULL CHECK (length(btrim(email)) BETWEEN 3 AND 320),
    role TEXT NOT NULL CHECK (role IN ('admin', 'editor', 'viewer')),
    invited_by UUID NOT NULL,
    token TEXT NOT NULL CHECK (length(token) BETWEEN 16 AND 256),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    accepted_at TIMESTAMPTZ,
    CONSTRAINT workspace_invite_workspace_email_key UNIQUE (workspace_id, email)
);

CREATE INDEX idx_workspace_invite_workspace
    ON workspace_invite (workspace_id, created_at DESC);

ALTER TABLE workspace_member ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspace_member FORCE ROW LEVEL SECURITY;
CREATE POLICY kairos_workspace_isolation ON workspace_member
    USING (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid)
    WITH CHECK (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid);

ALTER TABLE workspace_invite ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspace_invite FORCE ROW LEVEL SECURITY;
CREATE POLICY kairos_workspace_isolation ON workspace_invite
    USING (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid)
    WITH CHECK (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid);

-- Membership and invitations are workspace-private. Only the restricted API
-- login may touch them; they are never exposed through the generated PostgREST
-- API.
DO $$
DECLARE r TEXT;
BEGIN
    FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
            EXECUTE format('REVOKE ALL ON TABLE public.%I FROM %I', 'workspace_member', r);
        END IF;
    END LOOP;
END $$;
REVOKE ALL ON TABLE workspace_member FROM PUBLIC;
DO $$
DECLARE r TEXT;
BEGIN
    FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
            EXECUTE format('REVOKE ALL ON TABLE public.%I FROM %I', 'workspace_invite', r);
        END IF;
    END LOOP;
END $$;
REVOKE ALL ON TABLE workspace_invite FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE workspace_member TO kairos_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE workspace_invite TO kairos_app;

COMMENT ON TABLE workspace_member IS
    'A user''s role inside one workspace; the source of truth for authorization, never the JWT.';
COMMENT ON TABLE workspace_invite IS
    'Pending email invitations to a workspace; cannot grant ownership.';

-- Make every existing personal-workspace owner an active owner member. Written
-- so it is safe on a database that has already been migrated.
INSERT INTO workspace_member (workspace_id, user_id, role, status)
SELECT id, owner_user_id, 'owner', 'active'
FROM kairos_workspace
WHERE owner_user_id IS NOT NULL
ON CONFLICT (workspace_id, user_id) DO NOTHING;
