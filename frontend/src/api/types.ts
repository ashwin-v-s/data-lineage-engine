/**
 * TypeScript API contracts matching Kairos FastAPI Section 17 schemas.
 */

export type ReasoningState = 'OBSERVED' | 'REFUTED_FOR_RUN' | 'POSSIBLE' | 'UNKNOWN';

export type EntityType = 'TABLE' | 'VIEW' | 'JOB' | 'COLUMN' | 'STREAM';

export type RelationshipType = 'DERIVED_FROM' | 'READS' | 'WRITES' | 'TRANSFORMS';

export interface TemporalContext {
  as_of: string | null;
  recorded_as_of: string | null;
}

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, any>;
  request_id: string;
}

export interface HealthResponse {
  status: string;
  db: string;
  projection: string;
  version: string;
}

export interface EntitySummary {
  id: string;
  name: string;
  display_name?: string;
  entity_type: EntityType;
  namespace: string;
  description?: string;
  column_count?: number;
  row_count?: number;
}

// Matches backend SearchResult schema: {id, type, name}
export interface SearchResult {
  id: string;
  type: string;   // e.g. "TABLE", "COLUMN"
  name: string;   // qualified: "db.schema.table" or "db.schema.table.column"
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
}

// Matches backend LineageNode schema
export interface LineageNodeData {
  id: string;
  name: string;
  type: string;
  display_name?: string;
  namespace?: string;
  schema_version?: string;
}

// Matches backend LineageResponse schema
export interface LineageResponse {
  asset_id: string;
  nodes: LineageNodeData[];
  edges: Array<{ edge_id: string; source: string; target: string; granularity: string }>;
}

export interface CoverageVector {
  run_covered: boolean;
  operator_covered: boolean;
  source_dataset_covered: boolean;
  target_dataset_covered: boolean;
  source_columns_covered: string[];
  target_columns_covered: string[];
  branches_covered: boolean;
  coverage_mode: string;
  parser_status: string;
}

export interface EvidenceRef {
  evidence_id: string;
  type: string;
  source_system: string;
  event_time?: string;
  raw_payload_hash?: string;
}

// Matches backend DependencyStateResponse
export interface DependencyResponse {
  run_id: string;
  source: { column_id: string; display: string };
  target: { column_id: string; display: string };
  granularity: string;
  state: ReasoningState;
  interpretation: string;
  explanation: string;
  rule_id: string;
  reasoning_version: string;
  flags: string[];
  evidence: Array<{
    evidence_id: string;
    evidence_type: string;
    source_system: string;
    event_time?: string | null;
  }>;
  coverage?: {
    run_covered: boolean;
    operator_covered: boolean;
    source_dataset_covered: boolean;
    target_dataset_covered: boolean;
    branches_covered: boolean;
    coverage_mode: string;
    parser_status: string;
  } | null;
  temporal_context: { as_of: string; recorded_as_of: string };
  is_mock: boolean;
}

export interface RunResponse {
  run_id: string;
  job_name: string;
  namespace: string;
  started_at: string;
  completed_at?: string;
  status: string;
  event_count: number;
}

export interface EvidenceItem {
  evidence_id: string;
  evidence_type: string;
  source_system: string;
  event_time: string;
  payload_hash: string;
  details: Record<string, any>;
}

export interface EvidenceListResponse {
  dependency: string;
  records: EvidenceItem[];
  total: number;
}

export interface BenchmarkOracleRecord {
  run_id: string;
  source: string;
  target: string;
  expected_truth_label: 'PROPAGATED' | 'NOT_PROPAGATED';
  inferred_state: string;
  matches: boolean;
  oracle_hash: string;
}

export interface BenchmarkOracleResponse {
  warning: string;
  run_id: string;
  records: BenchmarkOracleRecord[];
  is_evaluation_mode: boolean;
}
