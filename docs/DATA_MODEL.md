# Data Model Documentation (M3)

**Author:** M3  
**Version:** 1.0  
**Migration:** 0001_core.sql  
**Last Updated:** 2026-09-21

---

## Overview

The Kairos data model implements **bitemporal lineage storage** with two independent time dimensions:

1. **Valid Time**: When a relationship existed in the real data pipeline
2. **Transaction Time**: When Kairos learned about or recorded that knowledge

This allows answering questions like:
- "What was the lineage on March 1st?" (valid time query)
- "What did we know on March 5th?" (transaction time query)
- "What was true on March 1st, according to what we knew on March 5th?" (both)

---

## Core Principles

###1. **PostgreSQL is the Authority**
- Single source of truth
- Neo4j is optional, derived, rebuildable

### 2. **Immutability**
- Raw events are NEVER updated or deleted
- Evidence records are immutable
- Changes create new versions, not modifications

### 3. **Half-Open Intervals**
- Both time axes use `[start, end)` semantics
- `valid_to = NULL` means "still valid"
- `transaction_to = NULL` means "current knowledge"

### 4. **Deterministic IDs**
- UUID v5 (namespace-based) for same-entity-same-ID
- Canonical identity tuples define uniqueness

---

## Entity Relationship Diagram

```
dataset (1) ─── (*) column_record
   │
   └──(*) evidence ──(*) lineage_edge ──(*) edge_temporal_version
                          │
                          └──(*) execution_state
```

---

## Table Descriptions

### `dataset`
**Purpose:** Canonical datasets with identity tuple  
**Owner:** M3  
**Immutable:** No (allows updates to metadata)

**Identity Tuple:**
```
(source_system, namespace, database_name, schema_name, name, asset_type)
```

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key (UUID v5 deterministic) |
| `source_system` | TEXT | Origin: 'sqlglot', 'dbt', 'openlineage', etc. |
| `namespace` | TEXT | System namespace (e.g., 'postgres://localhost:5432') |
| `database_name` | TEXT | Database name |
| `schema_name` | TEXT | Schema name (normalized to lowercase) |
| `name` | TEXT | Table/view/model name (normalized) |
| `asset_type` | TEXT | 'table', 'view', 'model', 'dataset' |
| `created_at` | TIMESTAMPTZ | When first recorded in Kairos |

**Unique Constraint:** All 6 identity components together

**Examples:**
- `('dbt', 'prod', 'analytics', 'public', 'users', 'table')`
- `('sqlglot', 'postgres://localhost', 'warehouse', 'staging', 'orders', 'view')`

---

### `column_record`
**Purpose:** Columns tied to dataset versions  
**Owner:** M3  
**Immutable:** No

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key (UUID v5 deterministic) |
| `dataset_id` | UUID FK | Parent dataset |
| `column_name` | TEXT | Column name (normalized to lowercase) |
| `data_type` | TEXT | Optional type (e.g., 'int', 'text') |
| `schema_version` | TEXT | Version identifier (default: 'v1') |
| `created_at` | TIMESTAMPTZ | When first recorded |

**Unique Constraint:** `(dataset_id, schema_version, column_name)`

**Why schema_version?**
- Handles schema evolution (columns added/removed/renamed)
- Same column name in v1 vs v2 gets different IDs

---

### `job` & `execution_run`
**Purpose:** Job and run tracking  
**Owner:** M3, used by M2

| Table | Key Columns | Description |
|-------|-------------|-------------|
| `job` | `(namespace, name)` | Unique job definition |
| `execution_run` | `run_id` (unique) | Specific execution instance |

**Notes:**
- `run_id` comes from source system if available
- Otherwise: deterministic fingerprint + UUID

---

### `raw_event`
**Purpose:** Immutable raw events from all sources  
**Owner:** M2 (writes), M3 (schema)  
**Immutable:** YES (trigger enforced)

| Column | Type | Description |
|--------|------|-------------|
| `event_id` | TEXT PK | Source event ID or SHA-256 of payload |
| `payload` | JSONB | Untouched original event |
| `payload_hash` | TEXT | SHA-256 for deduplication |
| `source_system` | TEXT | Origin system |
| `ingestion_time` | TIMESTAMPTZ | When Kairos received it |

**Immutability Enforcement:**
```sql
CREATE TRIGGER raw_event_immutable 
    BEFORE UPDATE OR DELETE ON raw_event
    FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
```

**Why Immutable?**
- Audit trail
- Reproducibility
- Never lose original evidence

---

### `evidence`
**Purpose:** Normalized evidence from raw events  
**Owner:** M1 (static), M2 (runtime), M3 (schema)  
**Immutable:** YES (by convention, not trigger)

| Column | Type | Description |
|--------|------|-------------|
| `evidence_id` | TEXT UNIQUE | Deterministic ID |
| `evidence_type` | TEXT | 'STATIC_DEPENDENCY', 'RUNTIME_POSITIVE', etc. |
| `source_system` | TEXT | Origin |
| `run_id` | TEXT | Null for static evidence |
| `source_column_id` | UUID FK | Source column (or dataset) |
| `target_column_id` | UUID FK | Target column (or dataset) |
| `granularity` | TEXT | 'DATASET', 'COLUMN', 'TUPLE_CELL' |
| `operator` | TEXT | SQL operator (e.g., 'CASE', 'JOIN') |
| `query_fingerprint` | TEXT | Hash of SQL query |
| `schema_fingerprint` | TEXT | Hash of schema |
| `parser_status` | TEXT | 'SUPPORTED', 'PARTIAL', 'UNSUPPORTED' |
| `coverage` | JSONB | Coverage vector (Section 14 of pack) |
| `event_time` | TIMESTAMPTZ | When event occurred in source |
| `effective_time` | TIMESTAMPTZ | When relationship became valid |
| `raw_event_id` | TEXT FK | Link to original raw event |

**Evidence Types:**
- `STATIC_DEPENDENCY`: From SQL analysis (M1)
- `DBT_DECLARED`: From dbt manifest (M1)
- `RUNTIME_POSITIVE`: Observed at runtime (M2)
- `RUNTIME_NEGATIVE_EVALUATION`: Complete negative evidence (M2)

**Critical Rule:**
> "No event was seen" is NEVER stored as a row. Only positive evidence and complete negative evaluations are stored.

---

### `lineage_edge`
**Purpose:** Logical lineage relationships (time-independent)  
**Owner:** M3

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID PK | Primary key |
| `source_id` | UUID | Source entity (dataset or column) |
| `target_id` | UUID | Target entity (dataset or column) |
| `granularity` | TEXT | Level of dependency |
| `operator_fingerprint` | TEXT | Optional operator hash |
| `query_fingerprint` | TEXT | Optional query hash |

**Unique Constraint:** All 5 columns together

**Relationship to Temporal Versions:**
- One logical edge → many temporal versions
- Separates "what relationship" from "when it existed"

---

### `edge_temporal_version` ⭐ **CORE TABLE**
**Purpose:** Bitemporal versions of lineage edges  
**Owner:** M3

| Column | Type | Description |
|--------|------|-------------|
| `version_id` | UUID PK | Primary key |
| `edge_id` | UUID FK | Logical edge |
| **VALID TIME** | | |
| `valid_from` | TIMESTAMPTZ | When relationship started in real pipeline |
| `valid_to` | TIMESTAMPTZ | When it ended (NULL = still valid) |
| `effective_time_status` | TEXT | 'KNOWN' or 'UNKNOWN' (D-14) |
| **TRANSACTION TIME** | | |
| `transaction_from` | TIMESTAMPTZ | When Kairos learned this |
| `transaction_to` | TIMESTAMPTZ | When knowledge was superseded (NULL = current) |
| **METADATA** | | |
| `evidence_id` | UUID FK | Evidence that created this version |
| `source_system` | TEXT | Origin system |
| `correction_of` | UUID FK | Links to prior version if this is a correction |

**Constraints:**
```sql
CHECK (valid_to IS NULL OR valid_from < valid_to)
CHECK (transaction_to IS NULL OR transaction_from < transaction_to)
```

**Indexes:**
- `(edge_id)` - lookup by edge
- `(valid_from, valid_to)` - valid time range queries
- `(transaction_from, transaction_to)` - transaction time range queries

---

### `execution_state`
**Purpose:** Derived 4-state results from reasoning engine  
**Owner:** M4 (writes), M3 (schema)

| Column | Type | Description |
|--------|------|-------------|
| `run_id` | TEXT | Execution run |
| `source_column_id` | UUID FK | Source column |
| `target_column_id` | UUID FK | Target column |
| `state` | TEXT | 'OBSERVED', 'REFUTED_FOR_RUN', 'POSSIBLE', 'UNKNOWN' |
| `reasoning_engine_version` | TEXT | Engine version that computed this |
| `evidence_ids` | TEXT[] | Array of evidence IDs used |
| `coverage` | JSONB | Coverage information |
| `temporal_context` | JSONB | Time context |
| `explanation` | TEXT | Human-readable reasoning |
| `warnings` | TEXT[] | Any warnings |
| `computed_at` | TIMESTAMPTZ | When computed |

**State Values:**
- `OBSERVED`: Positive runtime evidence seen
- `REFUTED_FOR_RUN`: Proven NOT to have happened in this run
- `POSSIBLE`: Could have happened, insufficient evidence
- `UNKNOWN`: Cannot determine

---

### `projection_outbox`
**Purpose:** Neo4j projection status (if Neo4j is enabled)  
**Owner:** M3  
**Status:** Optional, deferred until needed

| Column | Type | Description |
|--------|------|-------------|
| `entity_type` | TEXT | 'edge' or 'node' |
| `entity_id` | UUID | Entity to project |
| `operation` | TEXT | 'CREATE', 'UPDATE', 'DELETE' |
| `state` | TEXT | 'PENDING', 'APPLIED', 'FAILED', 'STALE' |
| `payload` | JSONB | Projection data |
| `applied_at` | TIMESTAMPTZ | When applied to Neo4j |
| `error_message` | TEXT | If failed |

**Pattern:** Outbox pattern for eventual consistency

---

## Temporal Query Examples

### Query 1: Current Lineage
```sql
-- What edges are currently valid?
SELECT e.source_id, e.target_id
FROM edge_temporal_version v
JOIN lineage_edge e ON v.edge_id = e.id
WHERE v.valid_from <= NOW()
  AND (v.valid_to IS NULL OR NOW() < v.valid_to)
  AND v.transaction_from <= NOW()
  AND (v.transaction_to IS NULL OR NOW() < v.transaction_to);
```

### Query 2: Historical Lineage (Valid Time)
```sql
-- What was valid on March 1st (latest knowledge)?
SELECT e.source_id, e.target_id
FROM edge_temporal_version v
JOIN lineage_edge e ON v.edge_id = e.id
WHERE v.valid_from <= '2026-03-01'
  AND (v.valid_to IS NULL OR '2026-03-01' < v.valid_to)
  AND v.transaction_to IS NULL;  -- Latest knowledge
```

### Query 3: Historical Knowledge (Transaction Time)
```sql
-- What did we know on March 5th about March 1st?
SELECT e.source_id, e.target_id
FROM edge_temporal_version v
JOIN lineage_edge e ON v.edge_id = e.id
WHERE v.valid_from <= '2026-03-01'
  AND (v.valid_to IS NULL OR '2026-03-01' < v.valid_to)
  AND v.transaction_from <= '2026-03-05'
  AND (v.transaction_to IS NULL OR '2026-03-05' < v.transaction_to);
```

### Query 4: Late Correction Example
```sql
-- Original belief: A->B valid indefinitely, learned Jan 2
INSERT INTO edge_temporal_version (...)
VALUES (..., '2026-01-01', NULL, '2026-01-02', NULL, ...);

-- Correction on Mar 10: actually ended Mar 1
-- Close old version's transaction time
UPDATE edge_temporal_version
SET transaction_to = '2026-03-10'
WHERE ...;

-- Insert corrected version
INSERT INTO edge_temporal_version (...)
VALUES (..., '2026-01-01', '2026-03-01', '2026-03-10', NULL, ...);
```

---

## Open Design Decisions

### D-14: Unknown Effective Time
**Status:** M3 proposes, M1 reviews

**Question:** How to handle edges with unknown effective time?

**Current Approach:**
- `effective_time_status` column: 'KNOWN' or 'UNKNOWN'
- Default: exclude from `as_of` queries
- Optional flag to include them with warnings

**Example:**
```sql
-- Exclude unknown effective time by default
WHERE effective_time_status = 'KNOWN'

-- Or include with warnings
SELECT *, 
  CASE WHEN effective_time_status = 'UNKNOWN' 
  THEN 'Warning: Effective time is unknown' 
  END AS warning
```

### D-13: URL Format (with M5)
**Status:** Pending

**Options:**
1. UUID-based: `/api/v1/lineage/6ba7b810-9dad-11d1-80b4-00c04fd430c8`
2. Name-based: `/api/v1/lineage/employees.salary`

**Tradeoff:**
- UUIDs: stable, no name collisions
- Names: human-readable, easier debugging

**Proposal:** Support both with redirect

---

## Migration Strategy

### Adding New Tables
Create `0002_add_xyz.sql`:
```sql
-- Migration 0002: Add XYZ feature
CREATE TABLE xyz (...);
```

### Modifying Tables
NEVER edit existing migration. Create new one:
```sql
-- Migration 0003: Add column to dataset
ALTER TABLE dataset ADD COLUMN metadata JSONB;
```

### Testing Migrations
```bash
# Test on clean database
dropdb kairos_test && createdb kairos_test
psql kairos_test < backend/migrations/0001_core.sql
psql kairos_test < backend/migrations/0002_add_xyz.sql
```

---

## Performance Considerations

### Indexes Created
- Identity lookups: `dataset (source_system, namespace, ...)`
- Traversal: `lineage_edge (source_id)`, `lineage_edge (target_id)`
- Temporal ranges: `edge_temporal_version (valid_from, valid_to)`
- Evidence tracking: `evidence (run_id)`, `evidence (source_column_id)`

### NOT Indexed Yet
- Full-text search on diagnostics
- JSONB fields (coverage, payload)
- Add as needed based on actual query patterns

### Future Optimization
- Partitioning by time ranges (if table grows large)
- Materialized views for common queries
- Connection pooling configuration

---

## References

- Architecture Pack: Sections 10, 11, 12
- Bitemporal Model: Pack Section 11
- Evidence Model: Pack Section 12
- Identity Rules: Pack Section 10

---

## Change Log

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-09-21 | Initial schema (migration 0001) |
