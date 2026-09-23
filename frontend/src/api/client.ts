/**
 * Centralized typed API client for the Kairos REST API.
 */
import {
  BenchmarkOracleResponse,
  DependencyResponse,
  EvidenceListResponse,
  HealthResponse,
  LineageResponse,
  RunResponse,
  SearchResponse,
} from './types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';
const API_PREFIX = `${BASE_URL}/api/v1`;

class ApiClientError extends Error {
  code: string;
  requestId?: string;
  details?: Record<string, any>;

  constructor(message: string, code: string = 'CLIENT_ERROR', requestId?: string, details?: Record<string, any>) {
    super(message);
    this.name = 'ApiClientError';
    this.code = code;
    this.requestId = requestId;
    this.details = details;
  }
}

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_PREFIX}${endpoint}`;
  try {
    const res = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...(options?.headers || {}),
      },
      ...options,
    });

    if (!res.ok) {
      let errPayload: any = null;
      try {
        errPayload = await res.json();
      } catch {
        // Not a JSON response
      }

      if (errPayload && errPayload.error) {
        throw new ApiClientError(
          errPayload.error.message || `Request failed with status ${res.status}`,
          errPayload.error.code,
          errPayload.error.request_id,
          errPayload.error.details
        );
      }

      throw new ApiClientError(`HTTP ${res.status}: ${res.statusText}`, `HTTP_${res.status}`);
    }

    return await res.json();
  } catch (err: any) {
    if (err instanceof ApiClientError) throw err;
    throw new ApiClientError(err.message || 'Network request failed', 'NETWORK_ERROR');
  }
}

export const api = {
  getHealth: () => request<HealthResponse>('/health'),

  search: (query: string, type?: string, limit = 20) => {
    const params = new URLSearchParams({ q: query, limit: String(limit) });
    if (type) params.append('type', type);
    return request<SearchResponse>(`/search?${params.toString()}`);
  },

  getLineage: (
    entity: string,
    params?: {
      as_of?: string | null;
      recorded_as_of?: string | null;
      granularity?: 'DATASET' | 'COLUMN';
      depth?: number;
    }
  ) => {
    const q = new URLSearchParams();
    if (params?.as_of) q.append('as_of', params.as_of);
    if (params?.recorded_as_of) q.append('recorded_as_of', params.recorded_as_of);
    if (params?.granularity) q.append('granularity', params.granularity);
    if (params?.depth) q.append('depth', String(params.depth));
    const qs = q.toString() ? `?${q.toString()}` : '';
    return request<LineageResponse>(`/lineage/${encodeURIComponent(entity)}${qs}`);
  },

  getLineageUpstream: (entity: string, depth = 1) =>
    request<LineageResponse>(`/lineage/${encodeURIComponent(entity)}/upstream?depth=${depth}`),

  getLineageDownstream: (entity: string, depth = 1) =>
    request<LineageResponse>(`/lineage/${encodeURIComponent(entity)}/downstream?depth=${depth}`),

  getRun: (runId: string) => request<RunResponse>(`/runs/${encodeURIComponent(runId)}`),

  getDependencyState: (
    runId: string,
    source: string,
    target: string,
    asOf?: string | null,
    recordedAsOf?: string | null
  ) => {
    const q = new URLSearchParams();
    if (asOf) q.append('as_of', asOf);
    if (recordedAsOf) q.append('recorded_as_of', recordedAsOf);
    const qs = q.toString() ? `?${q.toString()}` : '';
    return request<DependencyResponse>(
      `/runs/${encodeURIComponent(runId)}/dependency/${encodeURIComponent(source)}/${encodeURIComponent(target)}${qs}`
    );
  },

  getEvidence: (dependency: string) =>
    request<EvidenceListResponse>(`/evidence/${encodeURIComponent(dependency)}`),

  getBenchmarkOracle: (runId: string) =>
    request<BenchmarkOracleResponse>(`/evaluation/oracle/${encodeURIComponent(runId)}`),
};
