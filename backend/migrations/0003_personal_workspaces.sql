-- Personal workspaces and database-enforced tenant isolation.
-- Apply after 0001_core.sql and 0002_audit_ownership_metadata.sql.
-- Existing rows are retained in a private legacy workspace and are not
-- automatically exposed to the first user who signs in.

CREATE TABLE IF NOT EXISTS kairos_workspace (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_user_id UUID UNIQUE,
    name TEXT NOT NULL,
    is_legacy BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT kairos_workspace_legacy_owner_check
        CHECK (NOT is_legacy OR owner_user_id IS NULL)
);

INSERT INTO kairos_workspace (id, owner_user_id, name, is_legacy)
VALUES ('00000000-0000-4000-8000-000000000001', NULL, 'Legacy catalog', TRUE)
ON CONFLICT (id) DO NOTHING;

CREATE OR REPLACE FUNCTION kairos_ensure_personal_workspace(p_user_id UUID)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    workspace UUID;
BEGIN
    IF p_user_id IS NULL THEN
        RAISE EXCEPTION 'user id is required';
    END IF;

    INSERT INTO public.kairos_workspace (owner_user_id, name, is_legacy)
    VALUES (p_user_id, 'Personal workspace', FALSE)
    ON CONFLICT (owner_user_id) DO NOTHING;

    SELECT id INTO workspace
    FROM public.kairos_workspace
    WHERE owner_user_id = p_user_id AND NOT is_legacy;

    IF workspace IS NULL THEN
        RAISE EXCEPTION 'personal workspace could not be provisioned';
    END IF;
    RETURN workspace;
END;
$$;

REVOKE ALL ON FUNCTION kairos_ensure_personal_workspace(UUID) FROM PUBLIC;
DO $$
BEGIN
    EXECUTE format('GRANT EXECUTE ON FUNCTION public.kairos_ensure_personal_workspace(UUID) TO %I', current_user);
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'postgres') THEN
        GRANT EXECUTE ON FUNCTION public.kairos_ensure_personal_workspace(UUID) TO postgres;
    END IF;
END;
$$;

-- The API login must switch into this non-owner, non-BYPASSRLS role before it
-- queries business tables.  The migration runner's role remains privileged
-- for migrations and the narrowly scoped SECURITY DEFINER provisioning call.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kairos_app') THEN
        CREATE ROLE kairos_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
    END IF;
END;
$$;
ALTER ROLE kairos_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;

DO $$
BEGIN
    EXECUTE format('GRANT kairos_app TO %I', current_user);
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'postgres') THEN
        GRANT kairos_app TO postgres;
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA public TO kairos_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON
    dataset, column_record, job, execution_run, raw_event, evidence,
    lineage_edge, edge_temporal_version, execution_state, projection_outbox,
    team_member, owner_assignment, owner_request, audit_log, asset_version,
    audit_event, rollback_record
TO kairos_app;

-- Backfill all pre-workspace records to one unowned legacy workspace.  The
-- immutability trigger is disabled only during this controlled backfill.
ALTER TABLE raw_event DISABLE TRIGGER raw_event_immutable;

DO $$
DECLARE
    table_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'dataset', 'column_record', 'job', 'execution_run', 'raw_event',
        'evidence', 'lineage_edge', 'edge_temporal_version', 'execution_state',
        'projection_outbox', 'team_member', 'owner_assignment', 'owner_request',
        'audit_log', 'asset_version', 'audit_event', 'rollback_record'
    ] LOOP
        EXECUTE format('ALTER TABLE public.%I ADD COLUMN IF NOT EXISTS workspace_id UUID', table_name);
        EXECUTE format(
            'UPDATE public.%I SET workspace_id = %L::uuid WHERE workspace_id IS NULL',
            table_name, '00000000-0000-4000-8000-000000000001'
        );
        EXECUTE format(
            'ALTER TABLE public.%I ALTER COLUMN workspace_id SET DEFAULT NULLIF(current_setting(''kairos.workspace_id'', true), '''')::uuid',
            table_name
        );
        EXECUTE format('ALTER TABLE public.%I ALTER COLUMN workspace_id SET NOT NULL', table_name);
        EXECUTE format(
            'ALTER TABLE public.%I ADD CONSTRAINT %I FOREIGN KEY (workspace_id) REFERENCES public.kairos_workspace(id)',
            table_name, table_name || '_workspace_id_fkey'
        );
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY', table_name);
        EXECUTE format('DROP POLICY IF EXISTS kairos_workspace_isolation ON public.%I', table_name);
        EXECUTE format(
            'CREATE POLICY kairos_workspace_isolation ON public.%I USING (workspace_id = NULLIF(current_setting(''kairos.workspace_id'', true), '''')::uuid) WITH CHECK (workspace_id = NULLIF(current_setting(''kairos.workspace_id'', true), '''')::uuid)',
            table_name
        );
    END LOOP;
END;
$$;

ALTER TABLE raw_event ENABLE TRIGGER raw_event_immutable;

-- Natural identifiers are unique within a workspace rather than globally.
ALTER TABLE dataset DROP CONSTRAINT IF EXISTS dataset_source_system_namespace_database_name_schema_name_name_;
CREATE UNIQUE INDEX IF NOT EXISTS dataset_workspace_identity_key
    ON dataset (workspace_id, source_system, namespace, database_name, schema_name, name, asset_type);

ALTER TABLE job DROP CONSTRAINT IF EXISTS job_namespace_name_key;
CREATE UNIQUE INDEX IF NOT EXISTS job_workspace_identity_key ON job (workspace_id, namespace, name);

ALTER TABLE execution_run DROP CONSTRAINT IF EXISTS execution_run_run_id_key;
CREATE UNIQUE INDEX IF NOT EXISTS execution_run_workspace_run_id_key ON execution_run (workspace_id, run_id);

ALTER TABLE evidence DROP CONSTRAINT IF EXISTS evidence_evidence_id_key;
CREATE UNIQUE INDEX IF NOT EXISTS evidence_workspace_evidence_id_key ON evidence (workspace_id, evidence_id);

ALTER TABLE lineage_edge DROP CONSTRAINT IF EXISTS lineage_edge_source_id_target_id_granularity_operator_fingerpri;
CREATE UNIQUE INDEX IF NOT EXISTS lineage_edge_workspace_identity_key
    ON lineage_edge (workspace_id, source_id, target_id, granularity, operator_fingerprint, query_fingerprint);

ALTER TABLE team_member DROP CONSTRAINT IF EXISTS team_member_email_key;
CREATE UNIQUE INDEX IF NOT EXISTS team_member_workspace_email_key ON team_member (workspace_id, email);

COMMENT ON TABLE kairos_workspace IS 'Private personal workspaces; the legacy workspace preserves pre-isolation rows.';
COMMENT ON COLUMN dataset.workspace_id IS 'Tenant boundary enforced by PostgreSQL row-level security.';
