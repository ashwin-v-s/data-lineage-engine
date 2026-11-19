-- Migration 0016: workspace API keys and webhook delivery history.
-- Apply after 0013_membership_lifecycle.sql (and 0008 for the kairos_app role).
--
-- workspace_api_key holds only a SHA-256 hash of the bearer secret plus a
-- display prefix, so a leaked dump cannot be replayed against the API.
-- workspace_webhook holds the signing secret as the AES-256-GCM envelope
-- produced by backend/app/services/token_crypto.py, never plaintext.
-- workspace_webhook_delivery keeps the auditable outcome of every attempt.

CREATE TABLE public.workspace_api_key (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL
        DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid
        REFERENCES public.kairos_workspace(id) ON DELETE CASCADE,
    name TEXT NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 80),
    token_prefix TEXT NOT NULL CHECK (length(token_prefix) BETWEEN 8 AND 32),
    secret_hash TEXT NOT NULL CHECK (length(secret_hash) = 64),
    scopes TEXT[] NOT NULL DEFAULT ARRAY['read']::TEXT[]
        CHECK (scopes <@ ARRAY['read']::TEXT[]),
    created_by UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    CONSTRAINT workspace_api_key_workspace_name_key UNIQUE (workspace_id, name),
    CONSTRAINT workspace_api_key_secret_hash_key UNIQUE (secret_hash)
);

CREATE INDEX idx_workspace_api_key_workspace
    ON public.workspace_api_key (workspace_id, created_at DESC);

CREATE TABLE public.workspace_webhook (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL
        DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid
        REFERENCES public.kairos_workspace(id) ON DELETE CASCADE,
    created_by UUID NOT NULL,
    url TEXT NOT NULL CHECK (url ~ '^https://[^\s]+$'),
    description TEXT CHECK (description IS NULL OR length(description) <= 200),
    events TEXT[] NOT NULL CHECK (cardinality(events) BETWEEN 1 AND 16),
    signing_secret_ciphertext BYTEA NOT NULL,
    signing_key_version SMALLINT NOT NULL DEFAULT 1
        CHECK (signing_key_version BETWEEN 0 AND 255),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_delivery_at TIMESTAMPTZ,
    last_delivery_status INTEGER,
    last_delivery_ok BOOLEAN,
    CONSTRAINT workspace_webhook_url_key UNIQUE (workspace_id, url)
);

CREATE INDEX idx_workspace_webhook_workspace
    ON public.workspace_webhook (workspace_id, created_at DESC);

CREATE TABLE public.workspace_webhook_delivery (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    webhook_id UUID NOT NULL REFERENCES public.workspace_webhook(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL
        DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid
        REFERENCES public.kairos_workspace(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL CHECK (length(event_type) BETWEEN 1 AND 64),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    response_status INTEGER,
    response_excerpt TEXT,
    ok BOOLEAN NOT NULL,
    error TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_workspace_webhook_delivery_webhook
    ON public.workspace_webhook_delivery (workspace_id, webhook_id, created_at DESC);

ALTER TABLE public.workspace_api_key ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workspace_api_key FORCE ROW LEVEL SECURITY;
CREATE POLICY kairos_workspace_isolation ON public.workspace_api_key
    USING (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid)
    WITH CHECK (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid);

ALTER TABLE public.workspace_webhook ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workspace_webhook FORCE ROW LEVEL SECURITY;
CREATE POLICY kairos_workspace_isolation ON public.workspace_webhook
    USING (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid)
    WITH CHECK (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid);

ALTER TABLE public.workspace_webhook_delivery ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workspace_webhook_delivery FORCE ROW LEVEL SECURITY;
CREATE POLICY kairos_workspace_isolation ON public.workspace_webhook_delivery
    USING (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid)
    WITH CHECK (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid);

-- Credential material and outbound endpoints are workspace-private: only the
-- restricted API login may read them, never the generated PostgREST surface.
DO $$
DECLARE r TEXT;
BEGIN
    FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
            EXECUTE format('REVOKE ALL ON TABLE public.%I FROM %I', 'workspace_api_key', r);
            EXECUTE format('REVOKE ALL ON TABLE public.%I FROM %I', 'workspace_webhook', r);
            EXECUTE format('REVOKE ALL ON TABLE public.%I FROM %I', 'workspace_webhook_delivery', r);
        END IF;
    END LOOP;
END $$;

REVOKE ALL ON TABLE public.workspace_api_key FROM PUBLIC;
REVOKE ALL ON TABLE public.workspace_webhook FROM PUBLIC;
REVOKE ALL ON TABLE public.workspace_webhook_delivery FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.workspace_api_key TO kairos_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.workspace_webhook TO kairos_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.workspace_webhook_delivery TO kairos_app;

-- Key authentication runs before any workspace scope exists, so it cannot rely
-- on RLS. This SECURITY DEFINER function performs the only unscoped lookup in
-- the system: it resolves a hash to its workspace and records the use.
CREATE OR REPLACE FUNCTION public.kairos_authenticate_api_key(p_secret_hash TEXT)
RETURNS TABLE(
    key_id UUID,
    workspace_id UUID,
    key_name TEXT,
    scopes TEXT[],
    last_used_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
    IF p_secret_hash IS NULL OR length(p_secret_hash) <> 64 THEN
        RETURN;
    END IF;

    RETURN QUERY
    UPDATE public.workspace_api_key AS k
       SET last_used_at = now()
     WHERE k.secret_hash = p_secret_hash
       AND k.revoked_at IS NULL
    RETURNING k.id, k.workspace_id, k.name, k.scopes, k.last_used_at;
END;
$$;

REVOKE ALL ON FUNCTION public.kairos_authenticate_api_key(TEXT) FROM PUBLIC;
DO $$
BEGIN
    EXECUTE format(
        'GRANT EXECUTE ON FUNCTION public.kairos_authenticate_api_key(TEXT) TO %I',
        current_user
    );
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'postgres') THEN
        GRANT EXECUTE ON FUNCTION public.kairos_authenticate_api_key(TEXT) TO postgres;
    END IF;
END
$$;

COMMENT ON TABLE public.workspace_api_key IS
    'Workspace-scoped read-only API keys. Only a SHA-256 hash of the secret is stored.';
COMMENT ON COLUMN public.workspace_api_key.token_prefix IS
    'Display prefix shown in the UI so a key can be identified without revealing it.';
COMMENT ON TABLE public.workspace_webhook IS
    'Workspace-scoped outbound webhooks; the signing secret is stored only as an AES-256-GCM envelope.';
COMMENT ON TABLE public.workspace_webhook_delivery IS
    'Auditable outcome of every webhook delivery attempt, including failures.';
