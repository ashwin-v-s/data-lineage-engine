import React, { memo } from 'react';
import { EdgeProps, getBezierPath, EdgeLabelRenderer } from '@xyflow/react';

export const LineageEdgeComponent: React.FC<EdgeProps> = memo(({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  selected,
}) => {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const state = (data?.reasoning_state as string) || 'POSSIBLE';
  const hasD14 = Boolean(data?.d14_warning);

  let strokeColor = '#ffbf9e'; // POSSIBLE
  let strokeDasharray = '4,4';
  let strokeWidth = 1.5;

  if (state === 'OBSERVED') {
    strokeColor = '#8ed5ff';
    strokeDasharray = 'none';
    strokeWidth = 2.5;
  } else if (state === 'REFUTED_FOR_RUN') {
    strokeColor = '#ffb4ab';
    strokeDasharray = '3,3';
    strokeWidth = 1.5;
  } else if (state === 'UNKNOWN') {
    strokeColor = '#87929a';
    strokeDasharray = '4,4';
    strokeWidth = 1.5;
  }

  if (selected) {
    strokeColor = '#38bdf8';
    strokeWidth = 3;
  }

  return (
    <>
      <path
        id={id}
        className="react-flow__edge-path transition-colors"
        d={edgePath}
        stroke={strokeColor}
        strokeWidth={strokeWidth}
        strokeDasharray={strokeDasharray}
        fill="none"
      />

      <EdgeLabelRenderer>
        {/* D-14 Warning Hazard Pill */}
        {hasD14 && (
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              pointerEvents: 'all',
            }}
            className="z-30 flex items-center gap-1.5 px-3 py-1 rounded-xl bg-on-tertiary-container text-tertiary-fixed shadow-lg border border-tertiary-container font-mono-sm text-[10px] font-bold cursor-help"
            title="D-14: Temporal valid window unknown for this relationship — shown per active heuristic configuration"
          >
            <span className="material-symbols-outlined text-[14px] text-tertiary-fixed">warning</span>
            <span>D-14: TIME WINDOW UNKNOWN</span>
            <span className="w-1.5 h-1.5 rounded-full bg-tertiary-fixed animate-ping ml-0.5" />
          </div>
        )}

        {/* REFUTED Glyphed Circle Marker */}
        {state === 'REFUTED_FOR_RUN' && !hasD14 && (
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            }}
            className="w-4 h-4 rounded-full bg-error-container text-on-error-container flex items-center justify-center font-bold text-[9px]"
          >
            ⊘
          </div>
        )}
      </EdgeLabelRenderer>
    </>
  );
});
