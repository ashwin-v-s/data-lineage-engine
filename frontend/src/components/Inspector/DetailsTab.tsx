import React from 'react';
import { DependencyResponse } from '../../api/types';
import { BenchmarkOracleCard } from './BenchmarkOracleCard';

interface DetailsTabProps {
  selectedEdge: any | null;
  selectedNode: any | null;
  dependencyData?: DependencyResponse;
  validAt: string | null;
  knownAsOf: string | null;
  runId: string;
  benchmarkMode: boolean;
  onSwitchToEvidence: () => void;
}

export const DetailsTab: React.FC<DetailsTabProps> = ({
  selectedEdge,
  selectedNode,
  dependencyData,
  validAt,
  knownAsOf,
  runId,
  benchmarkMode,
  onSwitchToEvidence,
}) => {
  const isHistorical = Boolean(validAt);

  // If node selected
  if (selectedNode && !selectedEdge) {
    const node = selectedNode.data;
    return (
      <div className="flex flex-col gap-3.5">
        <div className="flex flex-col gap-1.5 p-3 rounded-xl bg-surface-container border border-outline-variant/30">
          <div className="flex items-center justify-between">
            <span className="font-label-caps text-[10px] text-outline uppercase font-semibold">
              Selected Entity
            </span>
            <span className="px-2 py-0.5 rounded-xl bg-primary-container text-on-primary-container font-mono-sm text-[10px] font-bold">
              {node.type?.toUpperCase()}
            </span>
          </div>
          <span className="font-headline-sm text-sm font-bold text-on-surface leading-tight mt-0.5">
            {node.display_name || node.name}
          </span>
          <div className="flex items-center gap-1.5 font-mono-sm text-xs text-outline mt-0.5">
            <span>Namespace: {node.namespace}</span>
            <span>•</span>
            <span>Version: {node.schema_version || 'v1.0'}</span>
          </div>
        </div>

        {/* Node Properties */}
        <div className="flex flex-col gap-2 p-3 rounded-xl bg-surface-container border border-outline-variant/30 font-mono-sm text-xs">
          <div className="flex items-center justify-between">
            <span className="text-outline">Canonical ID:</span>
            <span className="text-on-surface truncate ml-2 font-mono text-[11px]">{node.id}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-outline">Partition Strategy:</span>
            <span className="text-on-surface font-semibold">{node.metadata?.partition_strategy || 'None'}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-outline">Row Count:</span>
            <span className="text-tertiary font-bold">{node.metadata?.row_count?.toLocaleString() || '1,120,410'}</span>
          </div>
        </div>

        {/* Columns list */}
        {node.columns && node.columns.length > 0 && (
          <div className="flex flex-col gap-2 p-3 rounded-xl bg-surface-container border border-outline-variant/30">
            <span className="font-label-caps text-[10px] uppercase text-outline font-semibold">
              Schema Columns ({node.columns.length})
            </span>
            <div className="flex flex-col gap-1 max-h-48 overflow-y-auto font-mono-sm text-xs">
              {node.columns.map((c: string) => (
                <div key={c} className="flex items-center justify-between p-1.5 rounded bg-surface-container-high">
                  <span className="text-on-surface font-semibold">{c}</span>
                  <span className="text-outline text-[10px]">
                    {c === 'salary' ? 'INT' : c.includes('date') ? 'DATE' : 'VARCHAR'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  // Edge / Dependency view
  const state = dependencyData?.state || selectedEdge?.data?.reasoning_state || 'UNKNOWN';
  const interp =
    dependencyData?.interpretation ||
    (state === 'OBSERVED'
      ? 'Positive runtime evidence establishes observed propagation for this run.'
      : state === 'REFUTED_FOR_RUN'
      ? 'No propagation was established for this run under complete-evaluation conditions.'
      : state === 'POSSIBLE'
      ? 'Static analysis permits this dependency, but available evidence is insufficient to establish whether propagation occurred in this run.'
      : 'There is insufficient evidence to safely evaluate this dependency.');

  const sourceName = selectedEdge?.source || 'stg_customer_orders';
  const targetName = selectedEdge?.target || 'orders_fact';

  return (
    <div className="flex flex-col gap-3.5">
      {/* Active Historical Selection Card */}
      <div className="flex flex-col gap-1.5 p-3 rounded-xl bg-surface-container border border-outline-variant/30">
        <div className="flex items-center justify-between">
          <span className="font-label-caps text-[10px] text-outline uppercase font-semibold">
            Active Historical Selection
          </span>
          <span className="px-2 py-0.5 rounded-xl bg-surface-container-highest text-outline font-mono-sm text-[10px] font-bold">
            DERIVED_FROM ({isHistorical ? 'T_v RETROSPECTIVE' : 'LIVE'})
          </span>
        </div>
        <span className="font-headline-sm text-sm font-bold text-on-surface leading-tight mt-0.5">
          {sourceName} → {targetName}
        </span>
        <div className="flex items-center gap-1.5 font-mono-sm text-xs text-outline mt-0.5">
          <span className="text-outline font-semibold">gross_amount</span>
          <span className="material-symbols-outlined text-[14px]">trending_flat</span>
          <span className="text-on-surface font-semibold">net_revenue</span>
        </div>
      </div>

      {/* 4-State Reasoning Card with Verbatim Interpretation (Section 12) */}
      <div className="flex flex-col p-3 rounded-xl bg-surface-container border-2 border-dashed border-outline-variant/60 shadow-sm gap-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <span className="w-4 h-4 rounded-xl bg-surface-container-highest text-outline flex items-center justify-center font-bold text-[11px]">
              {state === 'OBSERVED' ? '✓' : state === 'REFUTED_FOR_RUN' ? '⊘' : state === 'POSSIBLE' ? '◐' : '?'}
            </span>
            <span className="font-mono-md text-xs font-bold text-outline">
              {state} ({isHistorical ? 'Historical T_v' : 'Live'})
            </span>
          </div>
          <span className="px-2 py-0.5 rounded-xl bg-surface-container-highest text-outline font-mono-sm text-[10px] font-bold">
            {dependencyData?.reasoning?.rule_id || (state === 'OBSERVED' ? 'Rule R2' : 'Rule R5')}
          </span>
        </div>
        <p className="font-body-sm text-xs text-on-surface leading-relaxed">{interp}</p>
        {isHistorical && (
          <div className="flex items-center justify-between bg-surface-container-lowest px-2.5 py-1 rounded-xl font-mono-sm text-[11px] border border-outline-variant/30 mt-0.5">
            <span className="text-outline">Prior Run Valid at Aug 15:</span>
            <span className="text-outline font-semibold truncate ml-1">run_2026_08_14_230000 (v1.9)</span>
          </div>
        )}
      </div>

      {/* Bitemporal Retrospective Slice Box (Section 7) */}
      <div className="flex flex-col gap-2 p-3 rounded-xl bg-surface-container border border-outline-variant/30">
        <div className="flex items-center justify-between">
          <span className="font-label-caps text-[10px] uppercase text-outline font-semibold">
            Bitemporal Retrospective Slice
          </span>
          <span className="px-1.5 py-0.5 rounded bg-tertiary-container text-on-tertiary-container font-mono-sm text-[10px] font-bold">
            {validAt ? 'Δ -39d 11h' : 'LIVE'}
          </span>
        </div>
        <div className="flex flex-col gap-1.5 font-mono-sm text-xs">
          <div className="flex items-center justify-between">
            <span className="text-outline">Query Valid Time (T_v):</span>
            <span className="text-tertiary font-bold">{validAt || 'CURRENT'}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-outline">Knowledge Horizon (T_k):</span>
            <span className="text-on-surface font-semibold">{knownAsOf || 'LATEST INGESTION'}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-outline">Edge Effective Range:</span>
            <span className="text-outline font-mono text-[11px]">[2026-09-01, ∞)</span>
          </div>
        </div>

        {/* D-14 Warning */}
        {selectedEdge?.data?.d14_warning && (
          <div className="flex items-start gap-2.5 p-3 rounded-xl bg-on-tertiary-container text-tertiary-fixed mt-1 border border-tertiary-container shadow-sm">
            <span className="material-symbols-outlined text-[18px] shrink-0 mt-0.5 text-tertiary-fixed">warning</span>
            <div className="flex flex-col font-mono-sm text-[11px] leading-tight">
              <span className="font-bold text-tertiary-fixed">D-14 Time Window Quality Warning</span>
              <span className="mt-1 text-tertiary-fixed/90 leading-relaxed">
                Time window unknown for this relationship — displayed per active heuristic configuration.
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Directional Adjacency */}
      <div className="flex flex-col gap-2 p-3 rounded-xl bg-surface-container border border-outline-variant/30">
        <div className="flex items-center justify-between">
          <span className="font-label-caps text-[10px] uppercase text-outline font-semibold">
            Directional Adjacency
          </span>
          <div className="flex items-center gap-2 font-mono-sm text-[11px]">
            <span className="text-primary font-semibold">Upstream: 4</span>
            <span className="text-outline">|</span>
            <span className="text-on-surface font-semibold">Downstream: 2</span>
          </div>
        </div>
        <div className="flex flex-col gap-1.5 font-mono-sm text-[11px]">
          <div className="flex items-center justify-between p-1.5 rounded-xl bg-surface-container-high">
            <span className="text-outline font-medium truncate">‹ gross_amount (Upstream source)</span>
            <span className="text-outline font-bold shrink-0">{isHistorical ? 'UNKNOWN AT T_v' : 'OBSERVED'}</span>
          </div>
          <div className="flex items-center justify-between p-1.5 rounded-xl bg-surface-container-high">
            <span className="text-on-surface font-medium truncate">‹ customer_id (Upstream source)</span>
            <span className="text-tertiary font-bold shrink-0">POSSIBLE</span>
          </div>
          <div className="flex items-center justify-between p-1.5 rounded-xl bg-surface-container-high">
            <span className="text-on-surface font-medium truncate">monthly_total (Downstream consumer) ›</span>
            <span className="text-primary font-bold shrink-0">DERIVED</span>
          </div>
        </div>
      </div>

      {/* Benchmark Oracle Block (Hazard Mode Only) */}
      <BenchmarkOracleCard runId={runId} enabled={benchmarkMode} />

      {/* Inspect Evidence Button */}
      <button
        className="w-full py-2 px-3 rounded-xl bg-primary text-on-primary font-mono-sm text-xs font-bold flex items-center justify-center gap-1.5 hover:bg-primary-container hover:text-on-primary-container transition-colors shadow-sm mt-1"
        onClick={onSwitchToEvidence}
        type="button"
      >
        <span>Inspect Evidence Records</span>
        <span className="material-symbols-outlined text-[15px]">arrow_forward</span>
      </button>
    </div>
  );
};
