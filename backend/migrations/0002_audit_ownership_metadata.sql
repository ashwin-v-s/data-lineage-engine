-- Migration 0002: Audit trail, ownership & metadata editing
-- Adds the tables/columns required by the audit, owner and metadata API routers.
-- NEVER edit this file after it's applied. Create 0003_*.sql for changes.

-- ============================================================================
-- DATASET: editable metadata + ownership columns
-- ============================================================================

ALTER TABLE dataset ADD COLUMN IF NOT EXISTS description      TEXT;
ALTER TABLE dataset ADD COLUMN IF NOT EXISTS tags             TEXT[];
ALTER TABLE dataset ADD COLUMN IF NOT EXISTS owner_name       TEXT;
ALTER TABLE dataset ADD COLUMN IF NOT EXISTS steward_name     TEXT;
ALTER TABLE dataset ADD COLUMN IF NOT EXISTS owner_id         TEXT;
ALTER TABLE dataset ADD COLUMN IF NOT EXISTS steward_id       TEXT;
ALTER TABLE dataset ADD COLUMN IF NOT EXISTS assigned_by      TEXT;
ALTER TABLE dataset ADD COLUMN IF NOT EXISTS assigned_at      TIMESTAMPTZ;
ALTER TABLE dataset ADD COLUMN IF NOT EXISTS last_modified_by TEXT;
ALTER TABLE dataset ADD COLUMN IF NOT EXISTS last_modified_at TIMESTAMPTZ;

-- ============================================================================
-- TEAM MEMBERS (assignable owners / stewards)
-- ============================================================================

CREATE TABLE IF NOT EXISTS team_member (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email        TEXT NOT NULL UNIQUE,
    name         TEXT NOT NULL,
    title        TEXT,
    department   TEXT,
    slack_handle TEXT,
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_team_member_active ON team_member(is_active);
CREATE INDEX IF NOT EXISTS idx_team_member_dept   ON team_member(department);

-- ============================================================================
-- OWNER ASSIGNMENT HISTORY
-- ============================================================================

CREATE TABLE IF NOT EXISTS owner_assignment (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dataset_id      UUID NOT NULL REFERENCES dataset(id) ON DELETE CASCADE,
    assignment_type TEXT NOT NULL,          -- 'OWNER' | 'STEWARD'
    previous_value  TEXT,
    new_value       TEXT NOT NULL,
    assigned_by     TEXT NOT NULL,
    assigned_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    reason          TEXT
);

CREATE INDEX IF NOT EXISTS idx_owner_assignment_dataset ON owner_assignment(dataset_id);

-- ============================================================================
-- OWNER REQUESTS (approval workflow)
-- ============================================================================

CREATE TABLE IF NOT EXISTS owner_request (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dataset_id       UUID NOT NULL REFERENCES dataset(id) ON DELETE CASCADE,
    requested_by     TEXT NOT NULL,
    requested_owner  TEXT NOT NULL,
    reason           TEXT,
    status           TEXT NOT NULL DEFAULT 'PENDING',  -- PENDING | APPROVED | REJECTED
    approved_by      TEXT,
    approved_at      TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at       TIMESTAMPTZ,
    CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED'))
);

CREATE INDEX IF NOT EXISTS idx_owner_request_dataset ON owner_request(dataset_id);
CREATE INDEX IF NOT EXISTS idx_owner_request_status  ON owner_request(status);

-- ============================================================================
-- AUDIT LOG (field-level change history)
-- ============================================================================

CREATE TABLE IF NOT EXISTS audit_log (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    asset_id      UUID NOT NULL REFERENCES dataset(id) ON DELETE CASCADE,
    field_name    TEXT NOT NULL,
    old_value     TEXT,
    new_value     TEXT,
    changed_by    TEXT NOT NULL,
    change_type   TEXT NOT NULL,          -- CREATE | UPDATE | DELETE | RESTORE
    change_reason TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_asset   ON audit_log(asset_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at);

-- ============================================================================
-- ASSET VERSIONS (snapshots for version history / diff)
-- ============================================================================

CREATE TABLE IF NOT EXISTS asset_version (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    asset_id       UUID NOT NULL REFERENCES dataset(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    snapshot_data  JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by     TEXT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    change_summary TEXT,
    is_release     BOOLEAN NOT NULL DEFAULT FALSE,
    release_notes  TEXT,
    UNIQUE (asset_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_asset_version_asset ON asset_version(asset_id);

-- ============================================================================
-- AUDIT EVENTS (high-level governance events for compliance reporting)
-- ============================================================================

CREATE TABLE IF NOT EXISTS audit_event (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    asset_id    UUID NOT NULL REFERENCES dataset(id) ON DELETE CASCADE,
    event_type  TEXT NOT NULL,
    severity    TEXT NOT NULL,            -- INFO | WARNING | CRITICAL
    description TEXT NOT NULL,
    metadata    JSONB,
    actor       TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_reviewed BOOLEAN NOT NULL DEFAULT FALSE,
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    CHECK (severity IN ('INFO', 'WARNING', 'CRITICAL'))
);

CREATE INDEX IF NOT EXISTS idx_audit_event_asset ON audit_event(asset_id);

-- ============================================================================
-- ROLLBACK RECORDS (version rollback workflow)
-- ============================================================================

CREATE TABLE IF NOT EXISTS rollback_record (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    asset_id        UUID NOT NULL REFERENCES dataset(id) ON DELETE CASCADE,
    from_version    INTEGER NOT NULL,
    to_version      INTEGER NOT NULL,
    rollback_reason TEXT NOT NULL,
    requested_by    TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'PENDING',  -- PENDING | APPROVED | EXECUTED | REJECTED
    approved_by     TEXT,
    approved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rollback_record_asset ON rollback_record(asset_id);

-- ============================================================================
-- SEED: sample team members (so the assignment modal is usable out of the box)
-- ============================================================================

INSERT INTO team_member (email, name, title, department, slack_handle, is_active) VALUES
    ('alice.chen@kairos.dev',   'Alice Chen',   'Data Platform Lead',   'Data Engineering', '@alice',  TRUE),
    ('bob.martin@kairos.dev',   'Bob Martin',   'Analytics Engineer',   'Data Engineering', '@bob',    TRUE),
    ('carol.diaz@kairos.dev',   'Carol Diaz',   'Head of Governance',   'Governance',       '@carol',  TRUE),
    ('dave.kim@kairos.dev',     'Dave Kim',     'ML Engineer',          'Data Science',     '@dave',   TRUE),
    ('erin.osei@kairos.dev',    'Erin Osei',    'VP Data',              'Leadership',       '@erin',   TRUE)
ON CONFLICT (email) DO NOTHING;
