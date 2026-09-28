import React from 'react';
import { useEvidenceQuery } from '../../api/queries';

interface EvidenceTabProps {
  dependencyId: string;
}

export const EvidenceTab: React.FC<EvidenceTabProps> = ({ dependencyId }) => {
  const { data, isLoading, error } = useEvidenceQuery(dependencyId || 'ev_stg_orders_01');

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center p-8 text-outline font-mono-sm text-xs gap-2">
        <span className="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        <span>Loading Evidence Dossier...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-3 bg-error-container/40 text-on-error-container rounded-xl font-mono-sm text-xs border border-error/40">
        Failed to fetch evidence dossier: {(error as Error).message}
      </div>
    );
  }

  const records = data?.records || [];

  return (
    <div className="flex-1 overflow-y-auto flex flex-col gap-2.5">
      <div className="flex items-center justify-between text-xs font-mono-sm pb-1 border-b border-outline-variant/30">
        <span className="text-outline">{records.length} Corroborated Records</span>
        <span className="px-2 py-0.5 rounded-xl bg-primary-container text-on-primary-container font-bold text-[10px]">
          RULE R2 / AST MATCH
        </span>
      </div>

      {records.length === 0 ? (
        <div className="p-4 text-center text-outline font-mono-sm text-xs">
          No corroborated evidence records found for this dependency.
        </div>
      ) : (
        records.map((rec) => (
          <div
            key={rec.evidence_id}
            className="p-2.5 rounded-xl bg-surface-container border border-primary/40 flex flex-col gap-1 font-mono-sm text-xs"
          >
            <div className="flex items-center justify-between">
              <span className="font-bold text-primary">{rec.evidence_id}</span>
              <span className="px-1.5 py-0.5 rounded-xl bg-surface-container-high text-on-surface text-[10px]">
                {rec.evidence_type}
              </span>
            </div>

            {/* AST or Execution details */}
            {rec.details?.ast ? (
              <p className="text-on-surface text-[11px] font-mono leading-relaxed mt-1 bg-surface-container-lowest p-2 rounded-xl">
                {rec.details.ast}
              </p>
            ) : rec.details?.parity ? (
              <p className="text-on-surface text-[11px] font-mono leading-relaxed mt-1 bg-surface-container-lowest p-2 rounded-xl">
                {rec.details.parity}
              </p>
            ) : (
              <p className="text-on-surface text-[11px] font-mono leading-relaxed mt-1 bg-surface-container-lowest p-2 rounded-xl">
                {rec.details?.dialect || 'Corroborated execution lineage proof.'}
              </p>
            )}

            <div className="flex items-center justify-between text-outline text-[10px] mt-1 pt-1 border-t border-surface-container-highest">
              <span>Source: {rec.source_system}</span>
              <span className="font-mono">Hash: {rec.payload_hash.slice(0, 16)}...</span>
            </div>
            <span className="text-outline text-[10px]">Event time: {rec.event_time}</span>
          </div>
        ))
      )}
    </div>
  );
};
