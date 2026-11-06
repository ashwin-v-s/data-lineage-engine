-- PROPOSAL ONLY / NOT APPLIED.
-- Migration 0011: M4 governance and evaluation storage.
-- Forward-only extension of 0009. Do not apply to the shared project until the
-- M1 migration owner reviews and approves it. No applied migration is changed.
-- All records are private to the transaction-local workspace and are granted
-- only to the restricted FastAPI role.

ALTER TABLE freshness_sla
    ADD COLUMN evaluation_schedule TEXT NOT NULL DEFAULT 'manual'
        CHECK (evaluation_schedule IN ('manual', '15m', 'hourly', 'daily')),
    ADD COLUMN paused BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE freshness_evaluation
    DROP CONSTRAINT IF EXISTS freshness_evaluation_state_check;
ALTER TABLE freshness_evaluation
    ADD CONSTRAINT freshness_evaluation_state_check
        CHECK (state IN ('HEALTHY', 'AT_RISK', 'LATE', 'STALE', 'UNKNOWN', 'PAUSED'));
ALTER TABLE freshness_evaluation
    ADD COLUMN evaluation_mode TEXT NOT NULL DEFAULT 'MANUAL'
        CHECK (evaluation_mode IN ('MANUAL', 'SCHEDULED'));
ALTER TABLE freshness_evaluation
    ADD COLUMN evidence_ref JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(evidence_ref) = 'object');

CREATE TABLE freshness_confirmation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid REFERENCES kairos_workspace(id),
    dataset_id UUID NOT NULL REFERENCES dataset(id),
    observed_at TIMESTAMPTZ NOT NULL,
    note TEXT NOT NULL CHECK (length(btrim(note)) BETWEEN 1 AND 1000),
    confirmed_by UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX freshness_confirmation_asset_time ON freshness_confirmation(workspace_id, dataset_id, observed_at DESC);

ALTER TABLE incident
    ADD COLUMN breach_type TEXT NOT NULL DEFAULT 'freshness',
    ADD COLUMN assigned_user_id UUID,
    ADD COLUMN resolution_detail JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(resolution_detail) = 'object'),
    ADD COLUMN escalation_level SMALLINT NOT NULL DEFAULT 0 CHECK (escalation_level >= 0),
    ADD COLUMN last_escalated_at TIMESTAMPTZ;

CREATE TABLE quality_assertion (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid REFERENCES kairos_workspace(id),
    dataset_id UUID NOT NULL REFERENCES dataset(id),
    name TEXT NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 160),
    assertion_type TEXT NOT NULL CHECK (assertion_type IN ('freshness','completeness','uniqueness','validity','schema','custom_sql')),
    definition JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(definition) = 'object'),
    severity TEXT NOT NULL DEFAULT 'MEDIUM' CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    schedule TEXT NOT NULL DEFAULT 'manual' CHECK (schedule IN ('manual','15m','hourly','daily','on_import')),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_by UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX quality_assertion_workspace_dataset ON quality_assertion(workspace_id, dataset_id, created_at DESC);

CREATE TABLE quality_result (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid REFERENCES kairos_workspace(id),
    assertion_id UUID NOT NULL REFERENCES quality_assertion(id),
    status TEXT NOT NULL CHECK (status IN ('PASS','FAIL','ERROR','SKIPPED')),
    checked_count BIGINT NOT NULL DEFAULT 0 CHECK (checked_count >= 0),
    failed_count BIGINT NOT NULL DEFAULT 0 CHECK (failed_count >= 0),
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(evidence) = 'object'),
    error_code TEXT,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX quality_result_workspace_assertion ON quality_result(workspace_id, assertion_id, evaluated_at DESC);

CREATE TABLE glossary_term (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid REFERENCES kairos_workspace(id),
    name TEXT NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 160),
    definition TEXT NOT NULL CHECK (length(btrim(definition)) BETWEEN 1 AND 4000),
    status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','APPROVED','DEPRECATED')),
    created_by UUID NOT NULL,
    approved_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, name)
);
CREATE TABLE term_assignment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid REFERENCES kairos_workspace(id),
    term_id UUID NOT NULL REFERENCES glossary_term(id),
    dataset_id UUID NOT NULL REFERENCES dataset(id),
    assigned_by UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, term_id, dataset_id)
);
CREATE TABLE pii_classification (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid REFERENCES kairos_workspace(id),
    dataset_id UUID NOT NULL REFERENCES dataset(id),
    column_id UUID REFERENCES column_record(id),
    classification TEXT NOT NULL CHECK (classification IN ('PII_SOURCE','PII_INHERITED','PII_MASKED','PII_POTENTIAL','PII_CLEARED','UNKNOWN')),
    evidence_state TEXT NOT NULL CHECK (evidence_state IN ('OBSERVED','POSSIBLE','UNKNOWN')),
    provenance JSONB NOT NULL CHECK (jsonb_typeof(provenance) = 'object'),
    classified_by UUID NOT NULL,
    reviewed_by UUID,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX pii_classification_workspace_asset ON pii_classification(workspace_id, dataset_id, created_at DESC);

CREATE TABLE domain (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid REFERENCES kairos_workspace(id),
    name TEXT NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 120),
    description TEXT NOT NULL DEFAULT '',
    owner_user_id UUID,
    created_by UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, name)
);
CREATE TABLE data_product (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid REFERENCES kairos_workspace(id),
    domain_id UUID REFERENCES domain(id),
    name TEXT NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 160),
    description TEXT NOT NULL DEFAULT '',
    owner_user_id UUID,
    status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','ACTIVE','DEPRECATED')),
    created_by UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, name)
);
CREATE TABLE product_asset (
    workspace_id UUID NOT NULL DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid REFERENCES kairos_workspace(id),
    product_id UUID NOT NULL REFERENCES data_product(id),
    dataset_id UUID NOT NULL REFERENCES dataset(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, product_id, dataset_id)
);
CREATE TABLE data_contract (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid REFERENCES kairos_workspace(id),
    product_id UUID NOT NULL REFERENCES data_product(id),
    version INTEGER NOT NULL CHECK (version > 0),
    enforcement_mode TEXT NOT NULL CHECK (enforcement_mode IN ('MONITOR','WARN','BLOCK')),
    clauses JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(clauses) = 'array'),
    created_by UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, product_id, version)
);
CREATE TABLE quality_contract_link (
    workspace_id UUID NOT NULL DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid REFERENCES kairos_workspace(id),
    assertion_id UUID NOT NULL REFERENCES quality_assertion(id),
    contract_id UUID NOT NULL REFERENCES data_contract(id),
    clause_key TEXT NOT NULL CHECK (length(btrim(clause_key)) BETWEEN 1 AND 120),
    PRIMARY KEY (workspace_id, assertion_id, contract_id, clause_key)
);

CREATE TABLE notification (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid REFERENCES kairos_workspace(id),
    recipient_user_id UUID NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('FRESHNESS_BREACH','QUALITY_FAILURE','INCIDENT_CREATED','SYNC_FAILURE','CREDENTIAL_EXPIRY','LINEAGE_CHANGE','PII_CHANGE')),
    title TEXT NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 240),
    detail JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(detail) = 'object'),
    action_path TEXT,
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX notification_inbox ON notification(workspace_id, recipient_user_id, created_at DESC);
CREATE TABLE notification_preference (
    workspace_id UUID NOT NULL DEFAULT NULLIF(current_setting('kairos.workspace_id', true), '')::uuid REFERENCES kairos_workspace(id),
    user_id UUID NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('FRESHNESS_BREACH','QUALITY_FAILURE','INCIDENT_CREATED','SYNC_FAILURE','CREDENTIAL_EXPIRY','LINEAGE_CHANGE','PII_CHANGE')),
    in_app BOOLEAN NOT NULL DEFAULT TRUE,
    email BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, user_id, event_type)
);

-- Keep every M4 table under forced workspace RLS and restricted-role access.
DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['freshness_confirmation','quality_assertion','quality_result','glossary_term','term_assignment','pii_classification','domain','data_product','product_asset','data_contract','quality_contract_link','notification','notification_preference'] LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format('CREATE POLICY kairos_workspace_isolation ON public.%I USING (workspace_id = NULLIF(current_setting(''kairos.workspace_id'', true), '''')::uuid) WITH CHECK (workspace_id = NULLIF(current_setting(''kairos.workspace_id'', true), '''')::uuid)', t);
    EXECUTE format('REVOKE ALL ON TABLE public.%I FROM PUBLIC', t);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.%I TO kairos_app', t);
  END LOOP;
END $$;

DO $$
DECLARE r TEXT; t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['freshness_confirmation','quality_assertion','quality_result','glossary_term','term_assignment','pii_classification','domain','data_product','product_asset','data_contract','quality_contract_link','notification','notification_preference'] LOOP
    FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
        EXECUTE format('REVOKE ALL ON TABLE public.%I FROM %I', t, r);
      END IF;
    END LOOP;
  END LOOP;
END $$;

COMMENT ON TABLE quality_result IS 'Counts and evidence only; raw row values are not retained by governance evaluation.';
COMMENT ON TABLE notification IS 'Workspace-scoped in-app notification; Realtime is only an invalidation signal followed by authorized API refetch.';
COMMENT ON TABLE pii_classification IS 'Evidence-backed classification metadata; classification never grants access to underlying data.';
