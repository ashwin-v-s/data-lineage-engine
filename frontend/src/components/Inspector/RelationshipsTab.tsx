import React from 'react';

interface RelationshipsTabProps {
  edges: any[];
  nodes: any[];
}

export const RelationshipsTab: React.FC<RelationshipsTabProps> = ({ edges, nodes }) => {
  return (
    <div className="flex-1 overflow-y-auto flex flex-col gap-2.5">
      <span className="font-label-caps text-[10px] uppercase text-outline font-semibold">
        Graph Neighborhood Adjacency ({edges.length} Edges)
      </span>

      <div className="flex flex-col gap-2 font-mono-sm text-xs">
        {edges.map((e) => {
          const state = e.data?.reasoning_state || 'POSSIBLE';
          const borderColor =
            state === 'OBSERVED'
              ? 'border-primary'
              : state === 'REFUTED_FOR_RUN'
              ? 'border-error'
              : 'border-tertiary';

          const textColor =
            state === 'OBSERVED'
              ? 'text-primary'
              : state === 'REFUTED_FOR_RUN'
              ? 'text-error'
              : 'text-tertiary';

          return (
            <div
              key={e.id}
              className={`p-2.5 rounded-xl bg-surface-container border-l-2 ${borderColor} flex items-center justify-between shadow-sm`}
            >
              <div>
                <div className="font-bold text-on-surface truncate">{e.source} → {e.target}</div>
                <div className="text-[10px] text-outline">Type: {e.data?.relationship_type || 'DERIVED_FROM'}</div>
              </div>
              <span className={`font-bold text-[10px] ${textColor}`}>{state.replace('_FOR_RUN', '')}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
