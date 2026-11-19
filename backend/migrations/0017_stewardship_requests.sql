-- Migration 0017: workspace stewardship requests.
-- Apply after 0016 (shared RLS/role conventions) and 0008 (kairos_app role).
--
-- A stewardship request is a workspace-scoped ask that a member raises and an
-- owner or admin resolves: either access to a catalog asset, or a proposed
-- glossary term. Nothing here grants source-system access; approval records a
-- decision so the requester can see the outcome.

CREATE TABLE public.stewardship_request (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL
        DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid
        REFERENCES public.kairos_workspace(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('access', 'glossary')),
    -- Catalog asset the request targets. Nullable because a glossary proposal
    -- can describe a term before the asset it belongs to is catalogued.
    dataset_id UUID,
    -- Asset identity captured at submission time, so the request still reads
    -- correctly after an asset is renamed or removed from the catalog.
    asset_label TEXT CHECK (asset_label IS NULL OR length(asset_label) <= 1024),
    -- Proposed glossary term for kind='glossary'.
    title TEXT CHECK (title IS NULL OR length(btrim(title)) BETWEEN 1 AND 160),
    detail TEXT NOT NULL CHECK (length(btrim(detail)) BETWEEN 1 AND 4000),
    requested_by UUID NOT NULL,
    requested_by_label TEXT CHECK (requested_by_label IS NULL OR length(requested_by_label) <= 320),
    status TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED')),
    resolution_note TEXT CHECK (resolution_note IS NULL OR length(resolution_note) <= 2000),
    resolved_by UUID,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT stewardship_request_target CHECK (
        (kind = 'access' AND asset_label IS NOT NULL)
        OR (kind = 'glossary' AND title IS NOT NULL)
    ),
    CONSTRAINT stewardship_request_resolution CHECK (
        (status = 'PENDING' AND resolved_by IS NULL AND resolved_at IS NULL)
        OR (status <> 'PENDING' AND resolved_by IS NOT NULL AND resolved_at IS NOT NULL)
    )
);

CREATE INDEX idx_stewardship_request_workspace_status
    ON public.stewardship_request (workspace_id, status, created_at DESC);

CREATE INDEX idx_stewardship_request_workspace_kind
    ON public.stewardship_request (workspace_id, kind, created_at DESC);

ALTER TABLE public.stewardship_request ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.stewardship_request FORCE ROW LEVEL SECURITY;
CREATE POLICY kairos_workspace_isolation ON public.stewardship_request
    USING (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid)
    WITH CHECK (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid);

-- Requests name workspace members and their reasons; only the restricted API
-- login may read them, never the generated PostgREST surface.
DO $$
DECLARE r TEXT;
BEGIN
    FOREACH r IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
            EXECUTE format('REVOKE ALL ON TABLE public.%I FROM %I', 'stewardship_request', r);
        END IF;
    END LOOP;
END $$;

REVOKE ALL ON TABLE public.stewardship_request FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.stewardship_request TO kairos_app;

COMMENT ON TABLE public.stewardship_request IS
    'Workspace-scoped access requests and glossary proposals with an owner/admin resolution.';
COMMENT ON COLUMN public.stewardship_request.asset_label IS
    'Asset identity captured at submission time; dataset_id may later be renamed or removed.';
