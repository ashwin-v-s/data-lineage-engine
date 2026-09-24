import React, { useCallback, useMemo } from 'react';
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  Node,
  Edge,
  MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from '@dagrejs/dagre';

import { LineageNodeComponent } from '../LineageNode/LineageNode';
import { LineageEdgeComponent } from '../LineageEdge/LineageEdge';

interface LineageCanvasProps {
  nodes: any[];
  edges: any[];
  onNodeClick: (node: any) => void;
  onEdgeClick: (edge: any) => void;
  granularity: 'DATASET' | 'COLUMN';
  onGranularityToggle: () => void;
  anchorId: string;
  onExpandDirection: (dir: 'upstream' | 'downstream', id: string) => void;
  onOpenPopover: (nodeId: string) => void;
}

const nodeTypes = {
  lineageNode: LineageNodeComponent,
};

const edgeTypes = {
  lineageEdge: LineageEdgeComponent,
};

// Dagre Layout calculation
function getLayoutedElements(nodes: Node[], edges: Edge[], direction = 'LR') {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({ rankdir: direction, nodesep: 70, ranksep: 180 });

  nodes.forEach((node) => {
    const isAnchor = (node.data as any)?.isAnchor;
    dagreGraph.setNode(node.id, {
      width: isAnchor ? 320 : 288,
      height: 140,
    });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - (dagreGraph.node(node.id).width / 2),
        y: nodeWithPosition.y - (dagreGraph.node(node.id).height / 2),
      },
    };
  });

  return { nodes: layoutedNodes, edges };
}

export const LineageCanvas: React.FC<LineageCanvasProps> = ({
  nodes: rawNodes,
  edges: rawEdges,
  onNodeClick,
  onEdgeClick,
  granularity,
  onGranularityToggle,
  anchorId,
  onExpandDirection,
  onOpenPopover,
}) => {
  // Convert API nodes to React Flow format
  const initialNodes: Node[] = useMemo(() => {
    return rawNodes.map((n) => {
      const isAnchor = n.id === anchorId || n.name === 'orders_fact';
      return {
        id: n.name || n.id,
        type: 'lineageNode',
        position: { x: 0, y: 0 },
        data: {
          ...n,
          isAnchor,
          onExpandDirection,
          onOpenPopover,
        },
      };
    });
  }, [rawNodes, anchorId, onExpandDirection, onOpenPopover]);

  // Convert API edges to React Flow format
  const initialEdges: Edge[] = useMemo(() => {
    return rawEdges.map((e) => ({
      id: e.edge_id,
      source: e.source,
      target: e.target,
      type: 'lineageEdge',
      data: {
        ...e,
        reasoning_state: e.reasoning_state,
        d14_warning: e.d14_warning,
      },
    }));
  }, [rawEdges]);

  // Calculate Dagre Layout
  const { nodes: layoutedNodes, edges: layoutedEdges } = useMemo(() => {
    return getLayoutedElements(initialNodes, initialEdges, 'LR');
  }, [initialNodes, initialEdges]);

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutedNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layoutedEdges);

  // Sync state if layouted elements change
  React.useEffect(() => {
    setNodes(layoutedNodes);
    setEdges(layoutedEdges);
  }, [layoutedNodes, layoutedEdges, setNodes, setEdges]);

  return (
    <main className="relative flex-1 bg-surface-container-lowest overflow-hidden flex flex-col shadow-inner">
      {/* Top HUD Floating Canvas Controls */}
      <div className="absolute top-3 left-4 right-4 z-20 flex flex-wrap items-center justify-between gap-3 pointer-events-none">
        {/* Granularity Mode Switch */}
        <div className="pointer-events-auto flex items-center p-0.5 rounded bg-surface-container/95 backdrop-blur-md shadow-md border border-outline-variant/40">
          <button
            className={`px-3 py-1 rounded font-mono-sm text-xs transition-colors ${
              granularity === 'DATASET'
                ? 'bg-primary-container text-on-primary-container font-bold shadow-sm'
                : 'text-outline hover:text-on-surface'
            }`}
            onClick={onGranularityToggle}
            type="button"
          >
            Dataset Lineage
          </button>
          <button
            className={`flex items-center gap-1.5 px-3 py-1 rounded font-mono-sm text-xs transition-colors ${
              granularity === 'COLUMN'
                ? 'bg-primary-container text-on-primary-container font-bold shadow-sm'
                : 'text-outline hover:text-on-surface'
            }`}
            onClick={onGranularityToggle}
            type="button"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-on-primary-container animate-pulse" />
            Column Lineage
          </button>
        </div>

        {/* Zoom, Fit, Isolate Controls */}
        <div className="pointer-events-auto flex items-center gap-1 bg-surface-container/95 backdrop-blur-md p-1 rounded shadow-md border border-outline-variant/40">
          <button className="flex items-center gap-1 px-2 py-1 rounded hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface font-mono-sm text-xs transition-colors">
            <span className="material-symbols-outlined text-[15px]">fit_screen</span>
            <span>Fit</span>
          </button>
          <button className="flex items-center gap-1 px-2 py-1 rounded bg-surface-container-high text-primary font-mono-sm text-xs transition-colors">
            <span className="material-symbols-outlined text-[15px]">hub</span>
            <span>Isolate</span>
          </button>
          <button className="flex items-center gap-1 px-2 py-1 rounded hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface font-mono-sm text-xs transition-colors">
            <span className="material-symbols-outlined text-[15px]">alt_route</span>
            <span>Trace Path</span>
          </button>
        </div>
      </div>

      {/* React Flow Viewport with Grid Background */}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={(_, node) => onNodeClick(node)}
        onEdgeClick={(_, edge) => onEdgeClick(edge)}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        minZoom={0.2}
        maxZoom={2}
      >
        <Background color="#87929a" gap={36} size={0.8} className="opacity-15" />
        <MiniMap
          nodeColor={(n: any) => (n.data?.isAnchor ? '#38bdf8' : '#273647')}
          maskColor="rgba(5, 20, 36, 0.7)"
          className="bg-surface-container-high/95 border border-surface-container-highest rounded shadow-lg !bottom-3 !right-4"
        />
        <Controls showInteractive={false} className="!bg-surface-container !border-outline-variant/40 !rounded" />
      </ReactFlow>
    </main>
  );
};
