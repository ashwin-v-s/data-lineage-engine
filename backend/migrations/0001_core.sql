-- Migration 0001: Core schema (M3)
-- Creates foundational tables for bitemporal lineage storage
-- NEVER edit this file after it's applied. Create 0002_*.sql for changes.

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- DATASETS AND COLUMNS
-- ============================================================================

CREATE TABLE dataset (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_system TEXT NOT NULL,
    namespace TEXT NOT NULL,
    database_name TEXT NOT NULL,
    schema_name TEXT NOT NULL,
    name TEXT NOT NULL,
    asset_type TEXT NOT NULL,  -- 'table', 'view', 'model', etc.
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_system, namespace, database_name, schema_name, name, asset_type)
);

CREATE INDEX idx_dataset_lookup ON dataset(source_system, namespace, database_name, schema_name, name);

CREATE TABLE column_record (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dataset_id UUID NOT NULL REFERENCES dataset(id),
    column_name TEXT NOT NULL,
    data_type TEXT,
    schema_version TEXT NOT NULL DEFAULT 'v1',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (dataset_id, schema_version, column_name)
);

CREATE INDEX idx_column_dataset ON column_record(dataset_id);

-- ============================================================================
-- JOBS AND RUNS
-- ============================================================================

CREATE TABLE job (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    namespace TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (namespace, name)
);

CREATE TABLE execution_run (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id TEXT NOT NULL UNIQUE,  -- from source system or generated
    job_id UUID NOT NULL REFERENCES job(id),
    status TEXT NOT NULL,  -- 'running', 'completed', 'failed'
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_run_job ON execution_run(job_id);

-- ============================================================================
-- RAW EVENTS (IMMUTABLE)
-- ============================================================================

CREATE TABLE raw_event (
    event_id TEXT PRIMARY KEY,  -- source event ID or SHA-256 of payload
    payload JSONB NOT NULL,
    payload_hash TEXT NOT NULL,
    source_system TEXT NOT NULL,
    ingestion_time TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_raw_event_source ON raw_event(source_system);
CREATE INDEX idx_raw_event_hash ON raw_event(payload_hash);

-- Make raw events IMMUTABLE
CREATE OR REPLACE FUNCTION forbid_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'raw evidence is immutable - create new version instead';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER raw_event_immutable 
    BEFORE UPDATE OR DELETE ON raw_event
    FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- ============================================================================
-- EVIDENCE (NORMALIZED FROM RAW EVENTS)
-- ============================================================================

CREATE TABLE evidence (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    evidence_id TEXT NOT NULL UNIQUE,
    evidence_type TEXT NOT NULL,  -- 'STATIC_DEPENDENCY', 'RUNTIME_POSITIVE', etc.
    source_system TEXT NOT NULL,
    run_id TEXT,
    source_dataset_id UUID REFERENCES dataset(id),
    target_dataset_id UUID REFERENCES dataset(id),
    source_column_id UUID REFERENCES column_record(id),
    target_column_id UUID REFERENCES column_record(id),
    granularity TEXT NOT NULL,  -- 'DATASET', 'COLUMN', 'TUPLE_CELL'
    operator TEXT,
    query_fingerprint TEXT,
    schema_fingerprint TEXT,
    expression_fingerprint TEXT,
    parser_status TEXT,  -- 'SUPPORTED', 'PARTIAL', 'UNSUPPORTED'
    coverage JSONB,
    event_time TIMESTAMPTZ,
    effective_time TIMESTAMPTZ,
    ingestion_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    diagnostics JSONB,
    raw_event_id TEXT REFERENCES raw_event(event_id)
);

CREATE INDEX idx_evidence_source ON evidence(source_column_id);
CREATE INDEX idx_evidence_target ON evidence(target_column_id);
CREATE INDEX idx_evidence_run ON evidence(run_id);
CREATE INDEX idx_evidence_type ON evidence(evidence_type);

-- ============================================================================
-- LINEAGE EDGES (LOGICAL)
-- ============================================================================

CREATE TABLE lineage_edge (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID NOT NULL,  -- can be dataset_id or column_id
    target_id UUID NOT NULL,  -- can be dataset_id or column_id
    granularity TEXT NOT NULL,
    operator_fingerprint TEXT,
    query_fingerprint TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_id, target_id, granularity, operator_fingerprint, query_fingerprint)
);

CREATE INDEX idx_edge_source ON lineage_edge(source_id);
CREATE INDEX idx_edge_target ON lineage_edge(target_id);

-- ============================================================================
-- TEMPORAL VERSIONS (BITEMPORAL)
-- ============================================================================

CREATE TABLE edge_temporal_version (
    version_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    edge_id UUID NOT NULL REFERENCES lineage_edge(id),
    
    -- VALID TIME: when the relationship existed in the real pipeline
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ,  -- NULL = still valid
    effective_time_status TEXT NOT NULL DEFAULT 'KNOWN',  -- 'KNOWN' or 'UNKNOWN'
    
    -- TRANSACTION TIME: when Kairos learned/recorded this knowledge
    transaction_from TIMESTAMPTZ NOT NULL,
    transaction_to TIMESTAMPTZ,  -- NULL = current knowledge
    
    -- Lineage source and metadata
    evidence_id UUID REFERENCES evidence(id),
    source_system TEXT NOT NULL,
    correction_of UUID REFERENCES edge_temporal_version(version_id),  -- links to prior version if correction
    
    -- Constraints: half-open intervals
    CHECK (valid_to IS NULL OR valid_from < valid_to),
    CHECK (transaction_to IS NULL OR transaction_from < transaction_to),
    CHECK (effective_time_status IN ('KNOWN', 'UNKNOWN'))
);

CREATE INDEX idx_temporal_edge ON edge_temporal_version(edge_id);
CREATE INDEX idx_temporal_valid ON edge_temporal_version(valid_from, valid_to);
CREATE INDEX idx_temporal_tx ON edge_temporal_version(transaction_from, transaction_to);
CREATE INDEX idx_temporal_evidence ON edge_temporal_version(evidence_id);

-- ============================================================================
-- DERIVED STATES (EXECUTION-CONDITIONED REASONING RESULTS)
-- ============================================================================

CREATE TABLE execution_state (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id TEXT NOT NULL,
    source_column_id UUID NOT NULL REFERENCES column_record(id),
    target_column_id UUID NOT NULL REFERENCES column_record(id),
    granularity TEXT NOT NULL,
    state TEXT NOT NULL,  -- 'OBSERVED', 'REFUTED_FOR_RUN', 'POSSIBLE', 'UNKNOWN'
    reasoning_engine_version TEXT NOT NULL,
    evidence_ids TEXT[] NOT NULL,  -- array of evidence IDs used
    coverage JSONB,
    temporal_context JSONB,
    explanation TEXT,
    warnings TEXT[],
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (state IN ('OBSERVED', 'REFUTED_FOR_RUN', 'POSSIBLE', 'UNKNOWN'))
);

CREATE INDEX idx_state_run ON execution_state(run_id);
CREATE INDEX idx_state_source ON execution_state(source_column_id);
CREATE INDEX idx_state_target ON execution_state(target_column_id);

-- ============================================================================
-- NEO4J PROJECTION STATUS (OPTIONAL)
-- ============================================================================

CREATE TABLE projection_outbox (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type TEXT NOT NULL,  -- 'edge', 'node'
    entity_id UUID NOT NULL,
    operation TEXT NOT NULL,  -- 'CREATE', 'UPDATE', 'DELETE'
    state TEXT NOT NULL DEFAULT 'PENDING',  -- 'PENDING', 'APPLIED', 'FAILED', 'STALE'
    payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    applied_at TIMESTAMPTZ,
    error_message TEXT,
    CHECK (state IN ('PENDING', 'APPLIED', 'FAILED', 'STALE'))
);

CREATE INDEX idx_projection_state ON projection_outbox(state);

-- ============================================================================
-- COMMENTS (DOCUMENTATION)
-- ============================================================================

COMMENT ON TABLE dataset IS 'Canonical datasets with identity tuple (source_system, namespace, database, schema, name, asset_type)';
COMMENT ON TABLE column_record IS 'Columns tied to dataset versions';
COMMENT ON TABLE raw_event IS 'Immutable raw events - never updated or deleted';
COMMENT ON TABLE evidence IS 'Normalized evidence from raw events';
COMMENT ON TABLE lineage_edge IS 'Logical lineage relationships (independent of time)';
COMMENT ON TABLE edge_temporal_version IS 'Bitemporal versions: valid_time × transaction_time';
COMMENT ON TABLE execution_state IS 'Derived 4-state results from reasoning engine';

COMMENT ON COLUMN edge_temporal_version.valid_from IS 'When the relationship started in the real pipeline';
COMMENT ON COLUMN edge_temporal_version.valid_to IS 'When it ended (NULL = still valid)';
COMMENT ON COLUMN edge_temporal_version.transaction_from IS 'When Kairos learned about this';
COMMENT ON COLUMN edge_temporal_version.transaction_to IS 'When this knowledge was superseded (NULL = current)';
COMMENT ON COLUMN edge_temporal_version.effective_time_status IS 'Whether effective time is known or unknown (D-14)';
