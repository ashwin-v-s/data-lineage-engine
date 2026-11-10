-- Migration 0015: workspace-scoped soft removal for catalog assets.
-- Removed assets disappear from normal dataset reads while lineage, evidence,
-- raw events, and audit history remain available for investigation.

BEGIN;

ALTER TABLE dataset
    ADD COLUMN IF NOT EXISTS removed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS removed_by UUID;

DROP POLICY IF EXISTS kairos_workspace_isolation ON dataset;

CREATE POLICY kairos_dataset_active_read ON dataset
    FOR SELECT
    USING (
        workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid
        AND removed_at IS NULL
    );

CREATE POLICY kairos_dataset_workspace_insert ON dataset
    FOR INSERT
    WITH CHECK (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid);

CREATE POLICY kairos_dataset_workspace_update ON dataset
    FOR UPDATE
    USING (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid)
    WITH CHECK (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid);

CREATE POLICY kairos_dataset_workspace_delete ON dataset
    FOR DELETE
    USING (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid);

COMMENT ON COLUMN dataset.removed_at IS
    'When set, the asset is hidden from workspace catalog reads; lineage and evidence history are retained.';
COMMENT ON COLUMN dataset.removed_by IS
    'Authenticated user UUID that removed the asset from active catalog reads.';

CREATE OR REPLACE FUNCTION public.kairos_remove_dataset(p_asset_id UUID, p_actor_id UUID)
RETURNS TABLE(asset_id UUID, asset_name TEXT)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
    v_workspace_id UUID;
    v_asset_name TEXT;
BEGIN
    v_workspace_id := NULLIF(current_setting('kairos.workspace_id', true), '')::UUID;
    IF v_workspace_id IS NULL OR p_actor_id IS NULL THEN
        RAISE EXCEPTION 'authenticated workspace and actor context are required';
    END IF;

    SELECT d.name INTO v_asset_name
    FROM public.dataset AS d
    WHERE d.id = p_asset_id
      AND d.workspace_id = v_workspace_id
      AND d.removed_at IS NULL
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN;
    END IF;

    UPDATE public.dataset
    SET removed_at = now(), removed_by = p_actor_id,
        last_modified_by = p_actor_id::TEXT, last_modified_at = now()
    WHERE id = p_asset_id AND workspace_id = v_workspace_id AND removed_at IS NULL;

    INSERT INTO public.audit_event
        (workspace_id, asset_id, event_type, severity, description, metadata, actor)
    VALUES
        (v_workspace_id, p_asset_id, 'ASSET_REMOVED', 'INFO',
         format('Asset %s was removed from the active catalog.', v_asset_name),
         jsonb_build_object('removal_mode', 'soft', 'preserved', ARRAY['lineage', 'evidence', 'raw events']),
         p_actor_id::TEXT);

    RETURN QUERY SELECT p_asset_id, v_asset_name;
END;
$$;

CREATE OR REPLACE FUNCTION public.kairos_upsert_dataset(
    p_source_system TEXT,
    p_namespace TEXT,
    p_database_name TEXT,
    p_schema_name TEXT,
    p_name TEXT,
    p_asset_type TEXT,
    p_description TEXT DEFAULT NULL,
    p_tags TEXT[] DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
    v_workspace_id UUID;
    v_asset_id UUID;
BEGIN
    v_workspace_id := NULLIF(current_setting('kairos.workspace_id', true), '')::UUID;
    IF v_workspace_id IS NULL THEN
        RAISE EXCEPTION 'authenticated workspace context is required';
    END IF;

    INSERT INTO public.dataset
        (workspace_id, source_system, namespace, database_name, schema_name,
         name, asset_type, description, tags, removed_at, removed_by)
    VALUES
        (v_workspace_id, p_source_system, p_namespace, p_database_name, p_schema_name,
         p_name, p_asset_type, p_description, COALESCE(p_tags, ARRAY[]::TEXT[]), NULL, NULL)
    ON CONFLICT (workspace_id, source_system, namespace, database_name, schema_name, name, asset_type)
    DO UPDATE SET
        description = COALESCE(EXCLUDED.description, public.dataset.description),
        tags = CASE WHEN cardinality(EXCLUDED.tags) > 0 THEN EXCLUDED.tags ELSE public.dataset.tags END,
        removed_at = NULL,
        removed_by = NULL
    RETURNING id INTO v_asset_id;

    RETURN v_asset_id;
END;
$$;

REVOKE ALL ON FUNCTION public.kairos_remove_dataset(UUID, UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.kairos_upsert_dataset(TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT[]) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.kairos_remove_dataset(UUID, UUID) TO kairos_app;
GRANT EXECUTE ON FUNCTION public.kairos_upsert_dataset(TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT[]) TO kairos_app;

COMMIT;
