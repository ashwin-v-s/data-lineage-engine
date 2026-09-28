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

export interface SearchResponse {
  query: string;
  results: EntitySummary[];
  total: number;
  cursor?: string;
}

export interface LineageNodeData {
  id: string;
  name: string;
  entity_type: EntityType;
  namespace: string;
  schema_version?: string;
  columns: string[];
  metadata: Record<string, any>;
}

export interface LineageEdgeData {
  edge_id: string;
  source_id: string;
  target_id: string;
  relationship_type: RelationshipType;
  granularity: 'DATASET' | 'COLUMN';
  reasoning_state: ReasoningState;
  operator?: string;
  d14_warning: boolean;
  temporal_range: {
    valid_from: string;
    valid_to: string | null;
    tx_from: string;
    tx_to: string | null;
  };
}

export interface LineageResponse {
  anchor_entity_id: string;
  nodes: LineageNodeData[];
  edges: LineageEdgeData[];
  temporal_context: TemporalContext;
  granularity: 'DATASET' | 'COLUMN';
  depth: number;
  truncated: boolean;
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

export interface DependencyResponse {
  run_id: string;
  source: { column_id: string; display: string };
  target: { column_id: string; display: string };
  granularity: string;
  state: ReasoningState;
  interpretation: string; // Locked verbatim 4-state sentence
  temporal_context: TemporalContext;
  coverage: CoverageVector;
  evidence: EvidenceRef[];
  reasoning: { engine_version: string; rule_id: string };
  warnings: string[];
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
