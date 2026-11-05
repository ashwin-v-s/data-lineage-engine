-- NOT VERIFIED APPLIED: asset_view and asset_star were absent from the live DB
-- as of 2026-10-30. Run `python scripts/db/verify_applied.py` before marking
-- this Applied. See docs/DECISION_LOG.md D12 for the verification process.
-- Migration 0005: per-user personalization records.
-- Apply after 0003_personal_workspaces.sql.
-- Read-only browse/preview paths must not write these tables; only an explicit
-- user action (opening an asset, starring it) does.

CREATE TABLE asset_view (
    workspace_id UUID NOT NULL
        DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid
        REFERENCES kairos_workspace(id),
    user_id UUID NOT NULL,
    asset_id UUID NOT NULL REFERENCES dataset(id) ON DELETE CASCADE,
    viewed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, user_id, asset_id)
);

CREATE INDEX idx_asset_view_user_recency
    ON asset_view (workspace_id, user_id, viewed_at DESC);

CREATE TABLE asset_star (
    workspace_id UUID NOT NULL
        DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid
        REFERENCES kairos_workspace(id),
    user_id UUID NOT NULL,
    asset_id UUID NOT NULL REFERENCES dataset(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, user_id, asset_id)
);

CREATE INDEX idx_asset_star_user_recency
    ON asset_star (workspace_id, user_id, created_at DESC);

ALTER TABLE asset_view ENABLE ROW LEVEL SECURITY;
ALTER TABLE asset_view FORCE ROW LEVEL SECURITY;
CREATE POLICY kairos_workspace_isolation ON asset_view
    USING (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid)
    WITH CHECK (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid);

ALTER TABLE asset_star ENABLE ROW LEVEL SECURITY;
ALTER TABLE asset_star FORCE ROW LEVEL SECURITY;
CREATE POLICY kairos_workspace_isolation ON asset_star
    USING (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid)
    WITH CHECK (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid);

-- Personalization is a user-private preference, never shared through the
-- generated PostgREST API. Only the restricted API login may touch it.
DO $$
DECLARE r TEXT;
BEGIN
    FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
            EXECUTE format('REVOKE ALL ON TABLE public.%I FROM %I', 'asset_view', r);
        END IF;
    END LOOP;
END $$;
REVOKE ALL ON TABLE asset_view FROM PUBLIC;
DO $$
DECLARE r TEXT;
BEGIN
    FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
            EXECUTE format('REVOKE ALL ON TABLE public.%I FROM %I', 'asset_star', r);
        END IF;
    END LOOP;
END $$;
REVOKE ALL ON TABLE asset_star FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE asset_view TO kairos_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE asset_star TO kairos_app;

COMMENT ON TABLE asset_view IS
    'Per-user recently viewed assets. Upserted on an explicit asset open.';
COMMENT ON TABLE asset_star IS
    'Per-user starred assets. Personal shortcut, not a shared governance signal.';
