-- Migration 0009: governance freshness and incident tables.
-- Apply after the latest applied migration (0008 or later).
-- Adds the workspace-scoped freshness_sla, freshness_evaluation, incident and
-- incident_event tables used by the freshness engine and the incident
-- workflow.  Evidence-first: a dataset is never reported LATE or STALE without
-- stored evidence, and exactly one incident exists per active breach.
-- APPLIED to the shared Supabase project; the 'freshness_sla',
-- 'freshness_evaluation', 'incident' and 'incident_event' tables exist live.

CREATE TABLE freshness_sla (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL
        DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid
        REFERENCES kairos_workspace(id),
    dataset_id UUID NOT NULL REFERENCES dataset(id),
    warn_after_minutes INTEGER NOT NULL CHECK (warn_after_minutes > 0),
    error_after_minutes INTEGER NOT NULL CHECK (error_after_minutes > 0),
    stale_after_minutes INTEGER
        CHECK (stale_after_minutes IS NULL OR stale_after_minutes > 0),
    signal TEXT NOT NULL
        CHECK (signal IN ('openlineage_run', 'dbt_run_results', 'updated_at', 'manual')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (error_after_minutes > warn_after_minutes),
    CONSTRAINT freshness_sla_workspace_dataset_key UNIQUE (workspace_id, dataset_id)
);

CREATE INDEX idx_freshness_sla_workspace
    ON freshness_sla (workspace_id, created_at DESC);

CREATE TABLE freshness_evaluation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL
        DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid
        REFERENCES kairos_workspace(id),
    dataset_id UUID NOT NULL REFERENCES dataset(id),
    sla_id UUID REFERENCES freshness_sla(id),
    state TEXT NOT NULL
        CHECK (state IN ('HEALTHY', 'AT_RISK', 'LATE', 'STALE', 'UNKNOWN')),
    age_minutes INTEGER,
    threshold_minutes INTEGER,
    reason TEXT NOT NULL,
    last_source_activity_at TIMESTAMPTZ,
    evidence_id UUID REFERENCES evidence(id),
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_freshness_evaluation_dataset
    ON freshness_evaluation (workspace_id, dataset_id, evaluated_at DESC);

CREATE TABLE incident (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL
        DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid
        REFERENCES kairos_workspace(id),
    dataset_id UUID NOT NULL REFERENCES dataset(id),
    title TEXT NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 256),
    severity TEXT NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    status TEXT NOT NULL DEFAULT 'DETECTED'
        CHECK (status IN ('DETECTED', 'ACKNOWLEDGED', 'INVESTIGATING', 'RESOLVED')),
    dedupe_key TEXT NOT NULL,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    acknowledged_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    owner_user_id UUID,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(detail) = 'object')
);

CREATE INDEX idx_incident_workspace_status
    ON incident (workspace_id, status, opened_at DESC);

-- At most ONE *open* incident per breach.  The predicate is what makes a later
-- re-breach open a fresh incident: once a row is RESOLVED it leaves the index,
-- so the same dedupe_key can be used again.  A plain UNIQUE constraint would
-- have silently swallowed every future breach for the same dataset.
CREATE UNIQUE INDEX incident_workspace_active_dedupe_key
    ON incident (workspace_id, dedupe_key)
    WHERE status <> 'RESOLVED';

CREATE TABLE incident_event (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL
        DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid
        REFERENCES kairos_workspace(id),
    incident_id UUID NOT NULL REFERENCES incident(id),
    event_type TEXT NOT NULL
        CHECK (event_type IN ('DETECTED', 'ACKNOWLEDGED', 'INVESTIGATING', 'RESOLVED', 'COMMENTED')),
    actor_user_id UUID,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(detail) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_incident_event_incident
    ON incident_event (workspace_id, incident_id, created_at);

ALTER TABLE freshness_sla ENABLE ROW LEVEL SECURITY;
ALTER TABLE freshness_sla FORCE ROW LEVEL SECURITY;
CREATE POLICY kairos_workspace_isolation ON freshness_sla
    USING (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid)
    WITH CHECK (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid);

ALTER TABLE freshness_evaluation ENABLE ROW LEVEL SECURITY;
ALTER TABLE freshness_evaluation FORCE ROW LEVEL SECURITY;
CREATE POLICY kairos_workspace_isolation ON freshness_evaluation
    USING (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid)
    WITH CHECK (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid);

ALTER TABLE incident ENABLE ROW LEVEL SECURITY;
ALTER TABLE incident FORCE ROW LEVEL SECURITY;
CREATE POLICY kairos_workspace_isolation ON incident
    USING (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid)
    WITH CHECK (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid);

ALTER TABLE incident_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE incident_event FORCE ROW LEVEL SECURITY;
CREATE POLICY kairos_workspace_isolation ON incident_event
    USING (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid)
    WITH CHECK (workspace_id = NULLIF(current_setting('kairos.workspace_id', true), '')::uuid);

-- Governance records are workspace-private. Only the restricted API login may
-- touch them; they are never exposed through the generated PostgREST API.
REVOKE ALL ON TABLE freshness_sla FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON TABLE freshness_evaluation FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON TABLE incident FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON TABLE incident_event FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE freshness_sla TO kairos_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE freshness_evaluation TO kairos_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE incident TO kairos_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE incident_event TO kairos_app;

COMMENT ON TABLE freshness_sla IS
    'Workspace-scoped freshness SLA for one dataset: warn/error/stale thresholds and the evidence signal that drives them.';
COMMENT ON TABLE freshness_evaluation IS
    'Append-only freshness verdict per dataset. Evidence-first: no stored activity yields UNKNOWN, never a false LATE/STALE.';
COMMENT ON TABLE incident IS
    'One incident per active breach, deduplicated by (workspace_id, dedupe_key); a return to HEALTHY resolves it.';
COMMENT ON TABLE incident_event IS
    'Append-only incident timeline: DETECTED, ACKNOWLEDGED, INVESTIGATING, RESOLVED, COMMENTED.';
COMMENT ON COLUMN incident.dedupe_key IS
    'Stable per-breach key (e.g. "freshness:<dataset_id>"), unique per workspace among non-RESOLVED incidents, so repeated evaluations never open duplicates but a resolved breach can recur.';
