-- Migration 0019: trust and collaboration surfaces.
-- Apply after 0018_dataset_identity_reconciliation.sql.
--
-- Adds the capabilities every established catalog/platform exposes but Kairos
-- did not persist:
--   * asset_certification — a steward's explicit trust endorsement, optional
--     expiry, with the certifier recorded. Presence of a live row is the
--     endorsement; expiry is evaluated at read time, never copied into a status
--     that could silently drift.
--   * asset_discussion   — threaded comments on an asset. A thread root can be
--     resolved; replies cannot, so "resolved" always describes the question.
--   * asset_engagement   — workspace-level open counts used for popularity /
--     trending. It deliberately stores no user id: per-user viewing history
--     stays in asset_view, which is private to that user.
--
-- Nothing here grants access to source data and no existing table is rewritten.

CREATE TABLE public.asset_certification (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL
        DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid
        REFERENCES public.kairos_workspace(id) ON DELETE CASCADE,
    dataset_id UUID NOT NULL REFERENCES public.dataset(id) ON DELETE CASCADE,
    note TEXT CHECK (note IS NULL OR length(btrim(note)) BETWEEN 1 AND 1000),
    certified_by UUID NOT NULL,
    certified_by_label TEXT CHECK (certified_by_label IS NULL OR length(certified_by_label) <= 320),
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT asset_certification_workspace_dataset_key UNIQUE (workspace_id, dataset_id)
);

CREATE INDEX idx_asset_certification_workspace_expiry
    ON public.asset_certification (workspace_id, expires_at);

CREATE TABLE public.asset_discussion (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL
        DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid
        REFERENCES public.kairos_workspace(id) ON DELETE CASCADE,
    dataset_id UUID NOT NULL REFERENCES public.dataset(id) ON DELETE CASCADE,
    parent_id UUID REFERENCES public.asset_discussion(id) ON DELETE CASCADE,
    author_id UUID NOT NULL,
    author_label TEXT CHECK (author_label IS NULL OR length(author_label) <= 320),
    body TEXT NOT NULL CHECK (length(btrim(body)) BETWEEN 1 AND 4000),
    resolved_at TIMESTAMPTZ,
    resolved_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- A reply is part of its parent's resolution and can never be resolved on
    -- its own; resolution always names both the time and the person.
    CONSTRAINT asset_discussion_reply_not_resolved CHECK (
        parent_id IS NULL
        OR (resolved_at IS NULL AND resolved_by IS NULL)
    ),
    CONSTRAINT asset_discussion_resolution_pair CHECK (
        (resolved_at IS NULL AND resolved_by IS NULL)
        OR (resolved_at IS NOT NULL AND resolved_by IS NOT NULL)
    )
);

CREATE INDEX idx_asset_discussion_asset
    ON public.asset_discussion (workspace_id, dataset_id, created_at);
CREATE INDEX idx_asset_discussion_open_threads
    ON public.asset_discussion (workspace_id, resolved_at)
    WHERE parent_id IS NULL;

CREATE TABLE public.asset_engagement (
    workspace_id UUID NOT NULL
        DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid
        REFERENCES public.kairos_workspace(id) ON DELETE CASCADE,
    dataset_id UUID NOT NULL REFERENCES public.dataset(id) ON DELETE CASCADE,
    view_count BIGINT NOT NULL DEFAULT 0 CHECK (view_count >= 0),
    last_viewed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, dataset_id)
);

CREATE INDEX idx_asset_engagement_popularity
    ON public.asset_engagement (workspace_id, view_count DESC);

ALTER TABLE public.asset_certification ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.asset_certification FORCE ROW LEVEL SECURITY;
CREATE POLICY kairos_workspace_isolation ON public.asset_certification
    USING (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid)
    WITH CHECK (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid);

ALTER TABLE public.asset_discussion ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.asset_discussion FORCE ROW LEVEL SECURITY;
CREATE POLICY kairos_workspace_isolation ON public.asset_discussion
    USING (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid)
    WITH CHECK (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid);

ALTER TABLE public.asset_engagement ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.asset_engagement FORCE ROW LEVEL SECURITY;
CREATE POLICY kairos_workspace_isolation ON public.asset_engagement
    USING (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid)
    WITH CHECK (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid);

-- Trust records name people and their opinions; only the restricted API login
-- may read or write them, never the generated PostgREST surface.
DO $$
DECLARE r TEXT; t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['asset_certification', 'asset_discussion', 'asset_engagement'] LOOP
        FOREACH r IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
                EXECUTE format('REVOKE ALL ON TABLE public.%I FROM %I', t, r);
            END IF;
        END LOOP;
        EXECUTE format('REVOKE ALL ON TABLE public.%I FROM PUBLIC', t);
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kairos_app') THEN
            EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.%I TO kairos_app', t);
        END IF;
    END LOOP;
END $$;

COMMENT ON TABLE public.asset_certification IS
    'A steward endorsement for one asset, optionally expiring. Certification is metadata trust, not an access grant.';
COMMENT ON TABLE public.asset_discussion IS
    'Threaded asset discussions. Only a thread root can be resolved; replies inherit that resolution.';
COMMENT ON TABLE public.asset_engagement IS
    'Workspace-level recorded asset opens for popularity ranking. Stores no user identity; per-user history stays in asset_view.';
