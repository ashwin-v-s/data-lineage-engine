-- Repair membership lifecycle for workspaces created after migration 0007.
-- Existing owners are backfilled, and every newly provisioned personal
-- workspace receives its owner membership in the same security-definer call.

INSERT INTO public.workspace_member (workspace_id, user_id, role, status)
SELECT w.id, w.owner_user_id, 'owner', 'active'
FROM public.kairos_workspace AS w
WHERE w.owner_user_id IS NOT NULL
ON CONFLICT (workspace_id, user_id)
DO UPDATE SET role = 'owner', status = 'active';

CREATE OR REPLACE FUNCTION public.kairos_ensure_personal_workspace(p_user_id UUID)
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

    INSERT INTO public.workspace_member (workspace_id, user_id, role, status)
    VALUES (workspace, p_user_id, 'owner', 'active')
    ON CONFLICT ON CONSTRAINT workspace_member_workspace_user_key
    DO UPDATE SET role = 'owner', status = 'active';

    RETURN workspace;
END;
$$;

REVOKE ALL ON FUNCTION public.kairos_ensure_personal_workspace(UUID) FROM PUBLIC;
DO $$
BEGIN
    EXECUTE format(
        'GRANT EXECUTE ON FUNCTION public.kairos_ensure_personal_workspace(UUID) TO %I',
        current_user
    );
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'postgres') THEN
        GRANT EXECUTE ON FUNCTION public.kairos_ensure_personal_workspace(UUID) TO postgres;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION public.kairos_list_user_workspaces(p_user_id UUID)
RETURNS TABLE(workspace_id UUID, workspace_name TEXT, role TEXT, is_current BOOLEAN)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
    SELECT w.id, w.name, m.role,
           w.id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid
    FROM public.workspace_member AS m
    JOIN public.kairos_workspace AS w ON w.id = m.workspace_id
    WHERE m.user_id = p_user_id
      AND m.status = 'active'
    ORDER BY w.created_at, w.name
$$;

REVOKE ALL ON FUNCTION public.kairos_list_user_workspaces(UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.kairos_list_user_workspaces(UUID) TO kairos_app;

CREATE OR REPLACE FUNCTION public.kairos_accept_workspace_invite(
    p_token TEXT,
    p_user_id UUID,
    p_user_email TEXT
)
RETURNS TABLE(workspace_id UUID, role TEXT)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    invite_row public.workspace_invite%ROWTYPE;
BEGIN
    SELECT * INTO invite_row
    FROM public.workspace_invite AS i
    WHERE i.token = p_token
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Invitation not found' USING ERRCODE = 'P0002';
    END IF;
    IF invite_row.accepted_at IS NOT NULL THEN
        RAISE EXCEPTION 'Invitation was already accepted' USING ERRCODE = '23505';
    END IF;
    IF invite_row.expires_at <= now() THEN
        RAISE EXCEPTION 'Invitation expired' USING ERRCODE = 'P0001';
    END IF;
    IF lower(btrim(invite_row.email)) <> lower(btrim(COALESCE(p_user_email, ''))) THEN
        RAISE EXCEPTION 'Sign in with the email address this invitation was sent to' USING ERRCODE = '42501';
    END IF;

    INSERT INTO public.workspace_member (workspace_id, user_id, role, status, invited_by)
    VALUES (invite_row.workspace_id, p_user_id, invite_row.role, 'active', invite_row.invited_by)
    ON CONFLICT ON CONSTRAINT workspace_member_workspace_user_key
    DO UPDATE SET role = EXCLUDED.role, status = 'active';

    UPDATE public.workspace_invite SET accepted_at = now() WHERE id = invite_row.id;
    RETURN QUERY SELECT invite_row.workspace_id, invite_row.role;
END;
$$;

REVOKE ALL ON FUNCTION public.kairos_accept_workspace_invite(TEXT, UUID, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.kairos_accept_workspace_invite(TEXT, UUID, TEXT) TO kairos_app;
