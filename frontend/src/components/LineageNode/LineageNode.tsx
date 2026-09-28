import React, { memo } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';

export interface LineageCustomNodeData {
  id: string;
  name: string;
  display_name: string;
  type: string;
  namespace: string;
  schema_version?: string;
  columns?: string[];
  metadata?: Record<string, any>;
  isAnchor?: boolean;
  reasoning_state?: string;
  onExpandDirection?: (direction: 'upstream' | 'downstream', entityId: string) => void;
  onOpenPopover?: (nodeId: string) => void;
}

export const LineageNodeComponent: React.FC<NodeProps> = memo(({ data, selected }) => {
  const node = data as unknown as LineageCustomNodeData;
  const isAnchor = node.isAnchor;
  const state = node.reasoning_state || 'POSSIBLE';

  // Badge styling per state
  let stateBadge = (
    <span className="px-1.5 py-0.5 rounded bg-tertiary-container text-on-tertiary-container font-mono-sm text-[10px] font-bold">
      ◐ POSSIBLE
    </span>
  );
  if (state === 'OBSERVED') {
    stateBadge = (
      <span className="px-1.5 py-0.5 rounded bg-primary text-on-primary font-mono-sm text-[10px] font-bold">
        ✓ OBSERVED
      </span>
    );
  } else if (state === 'REFUTED_FOR_RUN') {
    stateBadge = (
      <span className="px-1.5 py-0.5 rounded bg-error-container text-on-error-container font-mono-sm text-[10px] font-bold">
        ⊘ REFUTED
      </span>
    );
  } else if (state === 'UNKNOWN') {
    stateBadge = (
      <span className="px-1.5 py-0.5 rounded bg-surface-container-highest text-outline font-mono-sm text-[10px] font-semibold">
        ? UNKNOWN
      </span>
    );
  }

  // Handle icons
  let iconName = 'table_chart';
  if (node.type === 'view') iconName = 'visibility';
  if (node.type === 'job') iconName = 'terminal';
  if (node.type === 'stream') iconName = 'sensors';
  if (node.type === 'column') iconName = 'table_rows';

  return (
    <div
      className={`relative flex flex-col p-3 rounded-xl transition-all select-none cursor-pointer ${
        isAnchor
          ? 'w-80 bg-surface-container-high border-2 border-primary shadow-xl ring-2 ring-primary/30'
          : selected
          ? 'w-72 bg-surface-container border-2 border-primary shadow-lg'
          : 'w-72 bg-surface-container border border-surface-container-highest shadow-sm hover:border-outline'
      }`}
    >
      <Handle type="target" position={Position.Left} className="w-2 h-2 bg-primary border border-surface" />
      <Handle type="source" position={Position.Right} className="w-2 h-2 bg-primary border border-surface" />

      {/* Anchor Badge */}
      {isAnchor && (
        <div className="absolute -top-3.5 left-4 flex items-center gap-1 px-2.5 py-0.5 rounded-xl bg-primary text-on-primary font-label-caps text-[10px] font-bold uppercase tracking-wider shadow-md">
          <span className="material-symbols-outlined text-[13px] font-bold">anchor</span>
          <span>ANCHORED BASE ENTITY</span>
        </div>
      )}

      {/* Node Header */}
      <div className="flex items-center justify-between mb-1.5 mt-0.5">
        <div className="flex items-center gap-1">
          <span className="material-symbols-outlined text-outline text-[15px]">{iconName}</span>
          <span className="font-label-caps text-[10px] text-outline uppercase font-semibold">
            {node.type}
          </span>
        </div>
        {stateBadge}
      </div>

      {/* Node Name */}
      <span className="font-mono-sm text-xs font-bold text-on-surface truncate">
        {node.display_name || node.name}
      </span>
      <span className="font-mono-sm text-[10px] text-outline mt-0.5">
        {node.namespace} {node.schema_version ? `• ${node.schema_version}` : ''}
      </span>

      {/* Column Preview if present */}
      {node.columns && node.columns.length > 0 && (
        <div className="flex items-center justify-between mt-2 pt-1.5 px-2 py-1 bg-surface-container-lowest rounded border border-outline-variant/40">
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-primary" />
            <span className="font-mono-sm text-xs text-primary font-semibold">
              {node.metadata?.target_column || node.columns[0]}
            </span>
          </div>
          <span className="font-mono-sm text-[10px] text-outline">
            {node.metadata?.data_type || 'TEXT'}
          </span>
        </div>
      )}

      {/* Left / Right Expansion Affordance Pills for Anchor */}
      {isAnchor && (
        <div className="flex items-center justify-between mt-2 pt-2 border-t border-surface-container-highest font-mono-sm text-[10px]">
          <span
            className="text-outline hover:text-primary flex items-center gap-0.5 cursor-pointer"
            onClick={(e) => {
              e.stopPropagation();
              node.onExpandDirection?.('upstream', node.id);
            }}
          >
            <span className="material-symbols-outlined text-[12px] text-primary">arrow_back</span>
            Upstream (4)
          </span>
          <span
            className="text-outline hover:text-primary flex items-center gap-0.5 cursor-pointer"
            onClick={(e) => {
              e.stopPropagation();
              node.onExpandDirection?.('downstream', node.id);
            }}
          >
            Downstream (2)
            <span className="material-symbols-outlined text-[12px] text-primary">arrow_forward</span>
          </span>
        </div>
      )}

      {/* Downstream Expansion Trigger on Staging View */}
      {node.name === 'stg_customer_orders' && (
        <button
          className="absolute -right-3 top-1/2 -translate-y-1/2 z-30 flex items-center gap-0.5 px-2 py-1 rounded-full bg-surface-container-highest hover:bg-primary hover:text-on-primary text-outline border border-outline-variant/50 shadow-md font-mono-sm text-[10px] font-bold transition-all group"
          onClick={(e) => {
            e.stopPropagation();
            node.onOpenPopover?.(node.id);
          }}
          title="Downstream: 1 target link"
          type="button"
        >
          <span className="group-hover:text-on-primary">+ Downstream (1)</span>
          <span className="material-symbols-outlined text-[13px]">chevron_right</span>
        </button>
      )}
    </div>
  );
});
