-- Migration 0018: one catalog row per logical dataset.
--
-- Adapters used to write their own asset type and used the import artifact name
-- as the dataset's database name, so one table became a SOURCE + TABLE + MODEL
-- (and, for the SQL file, a second TABLE) with columns and edges split across
-- the variants.  Asset type is now a mutable attribute: identity is
-- (workspace, schema, name, kind group), where SOURCE/TABLE/VIEW/MODEL share
-- the DATASET group and dashboards/exposures/files keep their own group.
--
-- The migration also repairs the identity of rows written by the old import
-- path from the immutable raw_event that produced them (the asset's declared
-- schema, or the last namespace segment), then merges the duplicates.  All
-- child rows (columns, evidence, edges, governance) are moved to the survivor;
-- nothing is silently cascade-deleted before it is repointed.

BEGIN;

-- The old unique index includes the artifact name as database_name, so it
-- blocks repairing two variants into the same identity.  It is replaced by the
-- logical identity index at the end of this migration.
DROP INDEX IF EXISTS public.dataset_workspace_identity_key;

-- ── 1. Canonical asset type spelling ────────────────────────────────────────
UPDATE public.dataset
SET asset_type = CASE upper(btrim(asset_type))
        WHEN 'DATASET' THEN 'TABLE'
        WHEN 'SEED' THEN 'TABLE'
        WHEN 'SNAPSHOT' THEN 'MODEL'
        WHEN 'MATERIALIZED_VIEW' THEN 'VIEW'
        ELSE upper(btrim(asset_type))
    END
WHERE asset_type <> CASE upper(btrim(asset_type))
        WHEN 'DATASET' THEN 'TABLE'
        WHEN 'SEED' THEN 'TABLE'
        WHEN 'SNAPSHOT' THEN 'MODEL'
        WHEN 'MATERIALIZED_VIEW' THEN 'VIEW'
        ELSE upper(btrim(asset_type))
    END;

-- ── 2. Identity helpers ────────────────────────────────────────────────────
ALTER TABLE public.dataset
    ADD COLUMN IF NOT EXISTS name_key TEXT
        GENERATED ALWAYS AS (lower(btrim(name))) STORED,
    ADD COLUMN IF NOT EXISTS schema_key TEXT
        GENERATED ALWAYS AS (lower(btrim(schema_name))) STORED,
    ADD COLUMN IF NOT EXISTS identity_kind TEXT
        GENERATED ALWAYS AS (
            CASE
                WHEN upper(btrim(asset_type)) IN ('SOURCE', 'TABLE', 'VIEW', 'MODEL')
                    THEN 'DATASET'
                ELSE upper(btrim(asset_type))
            END
        ) STORED;

-- ── 3. Repair identity written by the old import path ─────────────────────
-- The old importer stored the import artifact reference in database_name and
-- the raw namespace in schema_name.  The immutable raw_event still holds the
-- asset's declared schema (dbt metadata.schema), so recover it there instead of
-- guessing.  Rows not produced by an import_run are left untouched.
UPDATE public.dataset AS d
SET database_name = '',
    schema_name = COALESCE(
        NULLIF(a->'metadata'->>'schema', ''),
        CASE
            WHEN d.namespace LIKE 'dbt/%'
                 AND array_length(string_to_array(d.namespace, '/'), 1) >= 3
                THEN split_part(d.namespace, '/', 3)
            -- A non-dbt namespace is already the schema path ("warehouse.raw").
            ELSE d.namespace
        END
    )
FROM public.import_run AS ir
JOIN public.raw_event AS re
  ON re.event_id = 'kairos-import:' || ir.id::text
CROSS JOIN LATERAL jsonb_array_elements(re.payload->'assets') AS a
WHERE d.workspace_id = ir.workspace_id
  AND d.database_name = ir.source_ref
  AND lower(d.name) = lower(a->>'name')
  AND upper(d.asset_type) = upper(a->>'type')
  AND lower(d.namespace) = lower(a->>'namespace');

-- ── 4. Merge duplicate rows for one logical dataset ───────────────────────
CREATE OR REPLACE FUNCTION public.kairos_merge_duplicate_datasets(
    p_workspace_id UUID DEFAULT NULL
)
RETURNS TABLE(kept_id UUID, merged_rows INTEGER)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
    group_row RECORD;
    survivor UUID;
    duplicate UUID;
    edge_row RECORD;
    new_source UUID;
    new_target UUID;
    surviving_edge UUID;
    merged INTEGER;
BEGIN
    FOR group_row IN
        SELECT d.workspace_id, d.schema_key, d.name_key, d.identity_kind
        FROM public.dataset AS d
        WHERE p_workspace_id IS NULL OR d.workspace_id = p_workspace_id
        GROUP BY d.workspace_id, d.schema_key, d.name_key, d.identity_kind
        HAVING count(*) > 1
    LOOP
        SELECT d.id INTO survivor
        FROM public.dataset AS d
        WHERE d.workspace_id = group_row.workspace_id
          AND d.schema_key = group_row.schema_key
          AND d.name_key = group_row.name_key
          AND d.identity_kind = group_row.identity_kind
        ORDER BY
            (SELECT count(*) FROM public.column_record c WHERE c.dataset_id = d.id) DESC,
            (SELECT count(*) FROM public.evidence e
              WHERE e.source_dataset_id = d.id OR e.target_dataset_id = d.id) DESC,
            d.created_at ASC, d.id ASC
        LIMIT 1;

        merged := 0;
        FOR duplicate IN
            SELECT d.id FROM public.dataset AS d
            WHERE d.workspace_id = group_row.workspace_id
              AND d.schema_key = group_row.schema_key
              AND d.name_key = group_row.name_key
              AND d.identity_kind = group_row.identity_kind
              AND d.id <> survivor
        LOOP
            -- Columns: repoint every reference to a same-named survivor column,
            -- then move the remaining columns with the dataset.
            UPDATE public.evidence AS e
               SET source_column_id = kc.id
              FROM public.column_record AS dc
              JOIN public.column_record AS kc
                ON kc.dataset_id = survivor
               AND kc.schema_version = dc.schema_version
               AND lower(kc.column_name) = lower(dc.column_name)
             WHERE e.source_column_id = dc.id AND dc.dataset_id = duplicate;

            UPDATE public.evidence AS e
               SET target_column_id = kc.id
              FROM public.column_record AS dc
              JOIN public.column_record AS kc
                ON kc.dataset_id = survivor
               AND kc.schema_version = dc.schema_version
               AND lower(kc.column_name) = lower(dc.column_name)
             WHERE e.target_column_id = dc.id AND dc.dataset_id = duplicate;

            UPDATE public.pii_classification AS pc
               SET column_id = kc.id
              FROM public.column_record AS dc
              JOIN public.column_record AS kc
                ON kc.dataset_id = survivor
               AND kc.schema_version = dc.schema_version
               AND lower(kc.column_name) = lower(dc.column_name)
             WHERE pc.column_id = dc.id AND dc.dataset_id = duplicate;

            UPDATE public.execution_state AS es
               SET source_column_id = kc.id
              FROM public.column_record AS dc
              JOIN public.column_record AS kc
                ON kc.dataset_id = survivor
               AND kc.schema_version = dc.schema_version
               AND lower(kc.column_name) = lower(dc.column_name)
             WHERE es.source_column_id = dc.id AND dc.dataset_id = duplicate;

            UPDATE public.execution_state AS es
               SET target_column_id = kc.id
              FROM public.column_record AS dc
              JOIN public.column_record AS kc
                ON kc.dataset_id = survivor
               AND kc.schema_version = dc.schema_version
               AND lower(kc.column_name) = lower(dc.column_name)
             WHERE es.target_column_id = dc.id AND dc.dataset_id = duplicate;

            UPDATE public.column_record AS dc
               SET dataset_id = survivor
             WHERE dc.dataset_id = duplicate
               AND NOT EXISTS (
                   SELECT 1 FROM public.column_record AS kc
                   WHERE kc.dataset_id = survivor
                     AND kc.schema_version = dc.schema_version
                     AND lower(kc.column_name) = lower(dc.column_name)
               );

            DELETE FROM public.column_record AS dc WHERE dc.dataset_id = duplicate;

            -- Dataset references without a uniqueness conflict.
            UPDATE public.evidence SET source_dataset_id = survivor WHERE source_dataset_id = duplicate;
            UPDATE public.evidence SET target_dataset_id = survivor WHERE target_dataset_id = duplicate;
            UPDATE public.freshness_confirmation SET dataset_id = survivor WHERE dataset_id = duplicate;
            UPDATE public.freshness_evaluation SET dataset_id = survivor WHERE dataset_id = duplicate;
            UPDATE public.incident SET dataset_id = survivor WHERE dataset_id = duplicate;
            UPDATE public.owner_assignment SET dataset_id = survivor WHERE dataset_id = duplicate;
            UPDATE public.owner_request SET dataset_id = survivor WHERE dataset_id = duplicate;
            UPDATE public.pii_classification SET dataset_id = survivor WHERE dataset_id = duplicate;
            UPDATE public.quality_assertion SET dataset_id = survivor WHERE dataset_id = duplicate;
            UPDATE public.rollback_record SET asset_id = survivor WHERE asset_id = duplicate;
            UPDATE public.audit_event SET asset_id = survivor WHERE asset_id = duplicate;
            UPDATE public.audit_log SET asset_id = survivor WHERE asset_id = duplicate;

            -- Governance/starred rows carry a per-pair uniqueness constraint.
            UPDATE public.freshness_sla AS s
               SET dataset_id = survivor
             WHERE s.dataset_id = duplicate
               AND NOT EXISTS (SELECT 1 FROM public.freshness_sla k
                                WHERE k.workspace_id = s.workspace_id AND k.dataset_id = survivor);
            DELETE FROM public.freshness_sla WHERE dataset_id = duplicate;

            UPDATE public.term_assignment AS t
               SET dataset_id = survivor
             WHERE t.dataset_id = duplicate
               AND NOT EXISTS (SELECT 1 FROM public.term_assignment k
                                WHERE k.workspace_id = t.workspace_id
                                  AND k.term_id = t.term_id AND k.dataset_id = survivor);
            DELETE FROM public.term_assignment WHERE dataset_id = duplicate;

            UPDATE public.product_asset AS p
               SET dataset_id = survivor
             WHERE p.dataset_id = duplicate
               AND NOT EXISTS (SELECT 1 FROM public.product_asset k
                                WHERE k.workspace_id = p.workspace_id
                                  AND k.product_id = p.product_id AND k.dataset_id = survivor);
            DELETE FROM public.product_asset WHERE dataset_id = duplicate;

            UPDATE public.asset_view AS v
               SET asset_id = survivor
             WHERE v.asset_id = duplicate
               AND NOT EXISTS (SELECT 1 FROM public.asset_view k
                                WHERE k.workspace_id = v.workspace_id
                                  AND k.user_id = v.user_id AND k.asset_id = survivor);
            DELETE FROM public.asset_view WHERE asset_id = duplicate;

            UPDATE public.asset_star AS s
               SET asset_id = survivor
             WHERE s.asset_id = duplicate
               AND NOT EXISTS (SELECT 1 FROM public.asset_star k
                                WHERE k.workspace_id = s.workspace_id
                                  AND k.user_id = s.user_id AND k.asset_id = survivor);
            DELETE FROM public.asset_star WHERE asset_id = duplicate;

            UPDATE public.asset_version AS v
               SET asset_id = survivor
             WHERE v.asset_id = duplicate
               AND NOT EXISTS (SELECT 1 FROM public.asset_version k
                                WHERE k.asset_id = survivor
                                  AND k.version_number = v.version_number);
            DELETE FROM public.asset_version WHERE asset_id = duplicate;

            -- Edges: move each edge to the survivor anchor, folding an edge into
            -- an identical survivor edge and carrying its temporal versions over.
            FOR edge_row IN
                SELECT le.id, le.source_id, le.target_id, le.granularity,
                       le.operator_fingerprint, le.query_fingerprint, le.workspace_id
                FROM public.lineage_edge AS le
                WHERE le.workspace_id = group_row.workspace_id
                  AND (le.source_id = duplicate OR le.target_id = duplicate)
                FOR UPDATE
            LOOP
                new_source := CASE WHEN edge_row.source_id = duplicate THEN survivor ELSE edge_row.source_id END;
                new_target := CASE WHEN edge_row.target_id = duplicate THEN survivor ELSE edge_row.target_id END;

                IF new_source = new_target THEN
                    DELETE FROM public.edge_temporal_version WHERE edge_id = edge_row.id;
                    DELETE FROM public.lineage_edge WHERE id = edge_row.id;
                    CONTINUE;
                END IF;

                SELECT k.id INTO surviving_edge
                FROM public.lineage_edge AS k
                WHERE k.workspace_id = edge_row.workspace_id
                  AND k.source_id = new_source
                  AND k.target_id = new_target
                  AND k.granularity = edge_row.granularity
                  AND k.operator_fingerprint IS NOT DISTINCT FROM edge_row.operator_fingerprint
                  AND k.query_fingerprint IS NOT DISTINCT FROM edge_row.query_fingerprint
                  AND k.id <> edge_row.id
                LIMIT 1;

                IF surviving_edge IS NULL THEN
                    UPDATE public.lineage_edge
                       SET source_id = new_source, target_id = new_target
                     WHERE id = edge_row.id;
                ELSE
                    UPDATE public.edge_temporal_version
                       SET edge_id = surviving_edge
                     WHERE edge_id = edge_row.id;
                    DELETE FROM public.lineage_edge WHERE id = edge_row.id;
                END IF;
            END LOOP;

            DELETE FROM public.dataset WHERE id = duplicate;
            merged := merged + 1;
        END LOOP;

        IF merged > 0 THEN
            kept_id := survivor;
            merged_rows := merged;
            RETURN NEXT;
        END IF;
    END LOOP;
END;
$$;

-- Operator-only repair helper: never granted to the application role, because
-- it accepts a workspace id (or NULL for all workspaces) and merges rows.
REVOKE ALL ON FUNCTION public.kairos_merge_duplicate_datasets(UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.kairos_merge_duplicate_datasets(UUID) FROM kairos_app;

-- Run the merge once for every workspace, then enforce the new identity.
SELECT public.kairos_merge_duplicate_datasets(NULL);

CREATE UNIQUE INDEX IF NOT EXISTS dataset_workspace_logical_identity_key
    ON public.dataset (workspace_id, schema_key, name_key, identity_kind);

COMMENT ON COLUMN public.dataset.name_key IS
    'Lower-cased dataset name; part of the logical identity with schema_key and identity_kind.';
COMMENT ON COLUMN public.dataset.schema_key IS
    'Lower-cased schema name; part of the logical identity with name_key and identity_kind.';
COMMENT ON COLUMN public.dataset.identity_kind IS
    'Reconciliation group: SOURCE/TABLE/VIEW/MODEL share DATASET; other types stay distinct.';
COMMENT ON COLUMN public.dataset.asset_type IS
    'Mutable declared type of the asset; it is not part of the dataset identity.';

-- ── 5. Upsert by logical identity (no asset_type in the key) ──────────────
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
    v_asset_type TEXT;
BEGIN
    v_workspace_id := NULLIF(current_setting('kairos.workspace_id', true), '')::UUID;
    IF v_workspace_id IS NULL THEN
        RAISE EXCEPTION 'authenticated workspace context is required';
    END IF;

    v_asset_type := CASE upper(btrim(COALESCE(p_asset_type, 'TABLE')))
        WHEN 'DATASET' THEN 'TABLE'
        WHEN 'SEED' THEN 'TABLE'
        WHEN 'SNAPSHOT' THEN 'MODEL'
        WHEN 'MATERIALIZED_VIEW' THEN 'VIEW'
        ELSE upper(btrim(COALESCE(p_asset_type, 'TABLE')))
    END;

    SELECT d.id INTO v_asset_id
    FROM public.dataset AS d
    WHERE d.workspace_id = v_workspace_id
      AND d.schema_key = lower(btrim(p_schema_name))
      AND d.name_key = lower(btrim(p_name))
      AND d.identity_kind = CASE
            WHEN v_asset_type IN ('SOURCE', 'TABLE', 'VIEW', 'MODEL') THEN 'DATASET'
            ELSE v_asset_type
          END
    FOR UPDATE;

    IF v_asset_id IS NOT NULL THEN
        UPDATE public.dataset AS d
        SET description = COALESCE(p_description, d.description),
            tags = CASE WHEN cardinality(COALESCE(p_tags, ARRAY[]::TEXT[])) > 0
                        THEN p_tags ELSE d.tags END,
            removed_at = NULL,
            removed_by = NULL
        WHERE d.id = v_asset_id;
        RETURN v_asset_id;
    END IF;

    BEGIN
        INSERT INTO public.dataset
            (workspace_id, source_system, namespace, database_name, schema_name,
             name, asset_type, description, tags, removed_at, removed_by)
        VALUES
            (v_workspace_id, p_source_system, p_namespace, '', p_schema_name,
             p_name, v_asset_type, p_description,
             COALESCE(p_tags, ARRAY[]::TEXT[]), NULL, NULL)
        RETURNING id INTO v_asset_id;
    EXCEPTION WHEN unique_violation THEN
        -- A concurrent import won the insert; use its row.
        SELECT d.id INTO v_asset_id
        FROM public.dataset AS d
        WHERE d.workspace_id = v_workspace_id
          AND d.schema_key = lower(btrim(p_schema_name))
          AND d.name_key = lower(btrim(p_name))
          AND d.identity_kind = CASE
                WHEN v_asset_type IN ('SOURCE', 'TABLE', 'VIEW', 'MODEL') THEN 'DATASET'
                ELSE v_asset_type
              END
        LIMIT 1;
    END;

    RETURN v_asset_id;
END;
$$;

REVOKE ALL ON FUNCTION public.kairos_upsert_dataset(TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT[]) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.kairos_upsert_dataset(TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT[]) TO kairos_app;

COMMIT;
