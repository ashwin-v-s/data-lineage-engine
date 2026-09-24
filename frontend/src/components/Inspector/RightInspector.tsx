import React, { useState } from 'react';
import { DetailsTab } from './DetailsTab';
import { EvidenceTab } from './EvidenceTab';
import { RelationshipsTab } from './RelationshipsTab';
import { DependencyResponse } from '../../api/types';

interface RightInspectorProps {
  isOpen: boolean;
  onToggle: () => void;
  selectedEdge: any | null;
  selectedNode: any | null;
  dependencyData?: DependencyResponse;
  validAt: string | null;
  knownAsOf: string | null;
  runId: string;
  benchmarkMode: boolean;
  edges: any[];
  nodes: any[];
}

export const RightInspector: React.FC<RightInspectorProps> = ({
  isOpen,
  onToggle,
  selectedEdge,
  selectedNode,
  dependencyData,
  validAt,
  knownAsOf,
  runId,
  benchmarkMode,
  edges,
  nodes,
}) => {
  const [activeTab, setActiveTab] = useState<'details' | 'evidence' | 'relationships'>('details');

  if (!isOpen) {
    return (
      <div className="w-12 shrink-0 bg-surface-container-low border-l border-outline-variant/30 flex flex-col items-center py-3 gap-3 z-20 select-none">
        <button
          className="text-outline hover:text-primary p-2 rounded-xl hover:bg-surface-container-high transition-colors"
          onClick={onToggle}
          title="Expand Inspector"
          type="button"
        >
          <span className="material-symbols-outlined text-[20px]">chevron_left</span>
        </button>
        <div className="w-6 h-px bg-outline-variant/30" />
        <button
          className={`p-2 rounded-xl transition-colors ${
            activeTab === 'details' ? 'text-primary bg-surface-container' : 'text-outline hover:text-on-surface'
          }`}
          onClick={() => {
            onToggle();
            setActiveTab('details');
          }}
          title="Inspect Details"
        >
          <span className="material-symbols-outlined text-[18px]">info</span>
        </button>
        <button
          className={`p-2 rounded-xl transition-colors ${
            activeTab === 'evidence' ? 'text-primary bg-surface-container' : 'text-outline hover:text-on-surface'
          }`}
          onClick={() => {
            onToggle();
            setActiveTab('evidence');
          }}
          title="Inspect Evidence"
        >
          <span className="material-symbols-outlined text-[18px]">policy</span>
        </button>
        <button
          className={`p-2 rounded-xl transition-colors ${
            activeTab === 'relationships' ? 'text-primary bg-surface-container' : 'text-outline hover:text-on-surface'
          }`}
          onClick={() => {
            onToggle();
            setActiveTab('relationships');
          }}
          title="Inspect Relationships"
        >
          <span className="material-symbols-outlined text-[18px]">account_tree</span>
        </button>
      </div>
    );
  }

  return (
    <aside className="w-[380px] shrink-0 bg-surface-container-low border-l border-outline-variant/30 flex flex-col shadow-sm overflow-hidden z-20 transition-all duration-200">
      {/* Top Tab Bar */}
      <div className="p-2.5 border-b border-outline-variant/30 bg-surface-container flex items-center justify-between gap-2">
        <div className="flex items-center p-0.5 rounded-xl bg-surface-container-lowest border border-outline-variant/40 flex-1" role="tablist">
          <button
            className={`flex-1 py-1 rounded-xl text-center font-mono-sm text-xs transition-all ${
              activeTab === 'details'
                ? 'font-bold bg-surface-container text-primary shadow-sm'
                : 'font-medium text-outline hover:text-on-surface'
            }`}
            onClick={() => setActiveTab('details')}
            role="tab"
          >
            Details
          </button>
          <button
            className={`flex-1 py-1 rounded-xl text-center font-mono-sm text-xs transition-all ${
              activeTab === 'evidence'
                ? 'font-bold bg-surface-container text-primary shadow-sm'
                : 'font-medium text-outline hover:text-on-surface'
            }`}
            onClick={() => setActiveTab('evidence')}
            role="tab"
          >
            Evidence (3)
          </button>
          <button
            className={`flex-1 py-1 rounded-xl text-center font-mono-sm text-xs transition-all ${
              activeTab === 'relationships'
                ? 'font-bold bg-surface-container text-primary shadow-sm'
                : 'font-medium text-outline hover:text-on-surface'
            }`}
            onClick={() => setActiveTab('relationships')}
            role="tab"
          >
            Relations ({edges.length})
          </button>
        </div>

        <button
          className="text-outline hover:text-on-surface p-1 rounded-xl hover:bg-surface-container-high transition-colors shrink-0"
          onClick={onToggle}
          title="Collapse Inspector"
          type="button"
        >
          <span className="material-symbols-outlined text-[18px]">chevron_right</span>
        </button>
      </div>

      {/* Tab Panels */}
      <div className="flex-1 overflow-y-auto p-3.5 flex flex-col gap-3.5">
        {activeTab === 'details' && (
          <DetailsTab
            selectedEdge={selectedEdge}
            selectedNode={selectedNode}
            dependencyData={dependencyData}
            validAt={validAt}
            knownAsOf={knownAsOf}
            runId={runId}
            benchmarkMode={benchmarkMode}
            onSwitchToEvidence={() => setActiveTab('evidence')}
          />
        )}

        {activeTab === 'evidence' && (
          <EvidenceTab dependencyId={selectedEdge?.data?.evidence_ids?.[0] || 'ev_stg_orders_01'} />
        )}

        {activeTab === 'relationships' && (
          <RelationshipsTab edges={edges} nodes={nodes} />
        )}
      </div>
    </aside>
  );
};
