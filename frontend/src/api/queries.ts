/**
 * TanStack React Query hooks for Kairos state management.
 */
import { useQuery } from '@tanstack/react-query';
import { api } from './client';

export function useHealthQuery() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => api.getHealth(),
    staleTime: 30_000,
  });
}

export function useSearchQuery(query: string, type?: string) {
  return useQuery({
    queryKey: ['search', query, type],
    queryFn: () => api.search(query, type),
    enabled: query.trim().length > 0,
    staleTime: 60_000,
  });
}

export function useLineageQuery(
  entity: string,
  asOf: string | null,
  recordedAsOf: string | null,
  granularity: 'DATASET' | 'COLUMN' = 'COLUMN',
  depth = 3
) {
  return useQuery({
    queryKey: ['lineage', entity, asOf, recordedAsOf, granularity, depth],
    queryFn: () => api.getLineage(entity, { as_of: asOf, recorded_as_of: recordedAsOf, granularity, depth }),
    staleTime: 10_000,
  });
}

export function useDependencyQuery(
  runId: string,
  source: string | null,
  target: string | null,
  asOf?: string | null,
  recordedAsOf?: string | null
) {
  return useQuery({
    queryKey: ['dependency', runId, source, target, asOf, recordedAsOf],
    queryFn: () => {
      if (!source || !target) throw new Error('Source and target required');
      return api.getDependencyState(runId, source, target, asOf, recordedAsOf);
    },
    enabled: Boolean(source && target && runId),
    staleTime: 10_000,
  });
}

export function useEvidenceQuery(dependency: string | null) {
  return useQuery({
    queryKey: ['evidence', dependency],
    queryFn: () => {
      if (!dependency) throw new Error('Dependency identifier required');
      return api.getEvidence(dependency);
    },
    enabled: Boolean(dependency),
    staleTime: 30_000,
  });
}

export function useBenchmarkOracleQuery(runId: string, enabled = false) {
  return useQuery({
    queryKey: ['evaluation', 'oracle', runId],
    queryFn: () => api.getBenchmarkOracle(runId),
    enabled: Boolean(enabled && runId),
    staleTime: 60_000,
  });
}
