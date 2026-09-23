import React, { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { Header } from './components/Header/Header';
import { BitemporalBar } from './components/BitemporalBar/BitemporalBar';
import { LeftFilterRail } from './components/LeftFilterRail/LeftFilterRail';
import { LineageCanvas } from './components/LineageCanvas/LineageCanvas';
import { RightInspector } from './components/Inspector/RightInspector';
import { DirectionalExpansionPopover } from './components/ExpansionPanel/DirectionalExpansionPopover';

import { useLineageQuery, useDependencyQuery } from './api/queries';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

const InvestigatorCockpit: React.FC = () => {
  // Bitemporal & Investigation State
  const [activeEntity, setActiveEntity] = useState<string>('orders_fact');
  const [runId, setRunId] = useState<string>('run_2026_09_23_093214');
  const [validAt, setValidAt] = useState<string | null>('2026-08-15T00:00:00Z');
  const [knownAsOf, setKnownAsOf] = useState<string | null>('2026-09-23T11:45:00Z');
  const [density, setDensity] = useState<'investigator' | 'research'>('investigator');
  const [granularity, setGranularity] = useState<'DATASET' | 'COLUMN'>('COLUMN');
  const [depth, setDepth] = useState<number>(3);
  const [benchmarkMode, setBenchmarkMode] = useState<boolean>(true);

  // Panel layout toggles
  const [leftRailOpen, setLeftRailOpen] = useState<boolean>(true);
  const [rightInspectorOpen, setRightInspectorOpen] = useState<boolean>(true);
  const [popoverNode, setPopoverNode] = useState<string | null>(null);

  // Selected graph items
  const [selectedNode, setSelectedNode] = useState<any | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<any | null>({
    id: 'edge_stg_to_fact',
    source: 'stg_customer_orders',
    target: 'orders_fact',
    data: {
      reasoning_state: 'OBSERVED',
      relationship_type: 'DERIVED_FROM',
      d14_warning: true,
      evidence_ids: ['ev_stg_orders_01', 'ev_stg_orders_02'],
    },
  });

  // State filters
  const [selectedStates, setSelectedStates] = useState<Record<string, boolean>>({
    OBSERVED: true,
    REFUTED_FOR_RUN: true,
    POSSIBLE: true,
    UNKNOWN: true,
  });

  const handleStateToggle = (s: string) => {
    setSelectedStates((prev) => ({ ...prev, [s]: !prev[s] }));
  };

  // 1. Fetch Lineage Graph from /api/v1/lineage/{entity}/graph
  const {
    data: lineageData,
    isLoading: lineageLoading,
    error: lineageError,
  } = useLineageQuery(activeEntity, validAt, knownAsOf, granularity, depth);

  // 2. Fetch Dependency Reasoning from /api/v1/runs/{run_id}/dependency/{source}/{target}
  const depSource = selectedEdge?.source || 'stg_customer_orders';
  const depTarget = selectedEdge?.target || 'orders_fact';
  const { data: dependencyData } = useDependencyQuery(runId, depSource, depTarget, validAt, knownAsOf);

  // Filter edges based on reasoning state selection
  const rawEdges = lineageData?.edges || [];
  const filteredEdges = rawEdges.filter((e) => selectedStates[e.reasoning_state] ?? true);
  const rawNodes = lineageData?.nodes || [];

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-surface text-on-surface">
      {/* 1. Header */}
      <Header
        density={density}
        onDensityChange={setDensity}
        runId={runId}
        benchmarkMode={benchmarkMode}
        onBenchmarkToggle={() => setBenchmarkMode((prev) => !prev)}
        onSelectEntity={(id) => {
          setActiveEntity(id);
          setSelectedNode(null);
        }}
      />

      {/* 2. Bitemporal Bar */}
      <BitemporalBar
        validAt={validAt}
        knownAsOf={knownAsOf}
        onValidAtChange={setValidAt}
        onKnownAsOfChange={setKnownAsOf}
        onResetToLive={() => {
          setValidAt(null);
          setKnownAsOf(null);
        }}
        isHistorical={Boolean(validAt)}
      />

      {/* 3. Main Investigation Workspace */}
      <div className="flex flex-1 w-full overflow-hidden relative">
        {/* Left Filter Rail */}
        <LeftFilterRail
          isOpen={leftRailOpen}
          onToggle={() => setLeftRailOpen((prev) => !prev)}
          selectedStates={selectedStates}
          onStateToggle={handleStateToggle}
          depth={depth}
          onDepthChange={setDepth}
          anchorName={activeEntity}
        />

        {/* Center Lineage Canvas */}
        {lineageLoading ? (
          <div className="flex-1 flex flex-col items-center justify-center bg-surface-container-lowest gap-3 text-outline font-mono-sm">
            <span className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            <span>Loading Lineage Graph from /api/v1...</span>
          </div>
        ) : lineageError ? (
          <div className="flex-1 flex items-center justify-center p-8 bg-surface-container-lowest">
            <div className="p-4 bg-error-container text-on-error-container rounded-xl font-mono-sm text-xs border border-error max-w-md">
              <span className="font-bold">Error loading lineage graph:</span>
              <p className="mt-1">{(lineageError as Error).message}</p>
            </div>
          </div>
        ) : (
          <LineageCanvas
            nodes={rawNodes}
            edges={filteredEdges}
            onNodeClick={(node) => {
              setSelectedNode(node);
              setSelectedEdge(null);
            }}
            onEdgeClick={(edge) => {
              setSelectedEdge(edge);
              setSelectedNode(null);
            }}
            granularity={granularity}
            onGranularityToggle={() =>
              setGranularity((prev) => (prev === 'COLUMN' ? 'DATASET' : 'COLUMN'))
            }
            anchorId={activeEntity}
            onExpandDirection={(dir, id) => {
              alert(`Expanding ${dir} lineage for ${id}`);
            }}
            onOpenPopover={(nodeId) => setPopoverNode(nodeId)}
          />
        )}

        {/* Right Inspector Panel */}
        <RightInspector
          isOpen={rightInspectorOpen}
          onToggle={() => setRightInspectorOpen((prev) => !prev)}
          selectedEdge={selectedEdge}
          selectedNode={selectedNode}
          dependencyData={dependencyData}
          validAt={validAt}
          knownAsOf={knownAsOf}
          runId={runId}
          benchmarkMode={benchmarkMode}
          edges={filteredEdges}
          nodes={rawNodes}
        />

        {/* Directional Expansion Popover */}
        <DirectionalExpansionPopover
          isOpen={Boolean(popoverNode)}
          nodeName={popoverNode || ''}
          onClose={() => setPopoverNode(null)}
          onApply={(opts) => {
            alert(`Applied expansion: ${opts.direction} with ${opts.rels.join(', ')}`);
          }}
        />
      </div>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <InvestigatorCockpit />
    </QueryClientProvider>
  );
};

export default App;
