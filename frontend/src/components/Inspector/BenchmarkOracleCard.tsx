import React from 'react';
import { useBenchmarkOracleQuery } from '../../api/queries';

interface BenchmarkOracleCardProps {
  runId: string;
  enabled: boolean;
}

export const BenchmarkOracleCard: React.FC<BenchmarkOracleCardProps> = ({ runId, enabled }) => {
  const { data, isLoading } = useBenchmarkOracleQuery(runId, enabled);

  if (!enabled) return null;

  return (
    <div className="flex flex-col gap-2 p-3 rounded-xl bg-surface-container-high border-2 border-secondary shadow-lg">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <span className="material-symbols-outlined text-secondary text-[16px]">fact_check</span>
          <span className="font-label-caps text-[10px] uppercase font-bold text-secondary">
            Ground Truth Oracle
          </span>
        </div>
        <span className="px-2 py-0.5 rounded-xl bg-secondary text-on-secondary font-mono-sm text-[10px] font-bold">
          BENCHMARK ACTIVE
        </span>
      </div>

      {isLoading ? (
        <span className="text-outline font-mono-sm text-[10px] animate-pulse">Loading oracle verification...</span>
      ) : data?.records && data.records.length > 0 ? (
        <>
          <div className="flex items-center justify-between font-mono-sm text-xs mt-0.5">
            <span className="text-outline">Expected Ground Truth:</span>
            <span className="text-secondary font-bold">
              {data.records[0].expected_truth_label}
            </span>
          </div>
          <div className="flex items-center justify-between font-mono-sm text-xs">
            <span className="text-outline">Kairos Inferred State:</span>
            <span className="text-outline font-semibold">
              {data.records[0].inferred_state} (Match {data.records[0].matches ? '✓' : '✗'})
            </span>
          </div>
          <div className="flex items-center justify-between font-mono-sm text-[10px] text-outline">
            <span>Oracle Hash:</span>
            <span className="font-mono truncate">{data.records[0].oracle_hash}</span>
          </div>
        </>
      ) : (
        <span className="text-outline font-mono-sm text-[10px]">No benchmark records for this run</span>
      )}
    </div>
  );
};
