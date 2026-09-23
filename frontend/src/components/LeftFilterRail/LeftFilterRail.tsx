import React from 'react';

interface LeftFilterRailProps {
  isOpen: boolean;
  onToggle: () => void;
  selectedStates: Record<string, boolean>;
  onStateToggle: (state: string) => void;
  depth: number;
  onDepthChange: (depth: number) => void;
  anchorName: string;
}

export const LeftFilterRail: React.FC<LeftFilterRailProps> = ({
  isOpen,
  onToggle,
  selectedStates,
  onStateToggle,
  depth,
  onDepthChange,
  anchorName,
}) => {
  if (!isOpen) {
    return (
      <button
        className="absolute left-0 top-3 z-30 bg-surface-container-high hover:bg-surface-container-highest text-primary p-1.5 rounded-r border border-l-0 border-outline-variant/40 shadow-lg"
        onClick={onToggle}
        title="Open Filter Rail"
        type="button"
      >
        <span className="material-symbols-outlined text-[18px]">tune</span>
      </button>
    );
  }

  return (
    <aside className="w-[240px] shrink-0 bg-surface-container-low border-r border-surface-container-highest flex flex-col p-3 gap-3.5 select-none overflow-y-auto transition-all duration-200 z-20">
      {/* Header */}
      <div className="flex items-center justify-between pb-1 border-b border-surface-container-highest">
        <div className="flex items-center gap-1.5">
          <span className="material-symbols-outlined text-primary text-[16px]">filter_alt</span>
          <span className="font-label-caps text-xs font-bold text-on-surface uppercase tracking-wider">
            Lineage Filters
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            className="text-outline hover:text-on-surface p-1 rounded-xl hover:bg-surface-container transition-colors"
            onClick={onToggle}
            title="Collapse Filter Rail"
            type="button"
          >
            <span className="material-symbols-outlined text-[16px]">chevron_left</span>
          </button>
        </div>
      </div>

      {/* Filter 1: Entity Types */}
      <div className="flex flex-col gap-1.5">
        <span className="font-label-caps text-[10px] uppercase text-outline font-semibold">Entity Types</span>
        <div className="flex flex-col gap-1">
          {['Table', 'View', 'Transformation Job', 'Column Entities'].map((ent, i) => (
            <label
              key={ent}
              className={`flex items-center justify-between px-2 py-1 rounded cursor-pointer transition-colors text-xs ${
                i === 3 ? 'bg-surface-container/60' : 'hover:bg-surface-container'
              }`}
            >
              <div className="flex items-center gap-2">
                <input
                  defaultChecked
                  className="accent-primary rounded-sm w-3.5 h-3.5 bg-surface-container-lowest border-outline-variant"
                  type="checkbox"
                />
                <span className={i === 3 ? 'text-primary font-semibold' : 'text-on-surface'}>{ent}</span>
              </div>
              <span
                className={`px-1.5 py-0.2 rounded font-mono-sm text-[10px] ${
                  i === 3
                    ? 'bg-primary-container text-on-primary-container font-bold'
                    : 'bg-surface-container-high text-on-surface'
                }`}
              >
                {[4, 2, 3, 12][i]}
              </span>
            </label>
          ))}
        </div>
      </div>

      {/* Filter 2: Relationship Types */}
      <div className="flex flex-col gap-1.5">
        <span className="font-label-caps text-[10px] uppercase text-outline font-semibold">Relationship Type</span>
        <div className="flex flex-col gap-1 text-xs">
          {[
            { name: 'DERIVED_FROM', count: 9 },
            { name: 'READS', count: 5 },
            { name: 'WRITES', count: 3 },
          ].map((rel, i) => (
            <label
              key={rel.name}
              className="flex items-center justify-between px-2 py-1 rounded bg-surface-container cursor-pointer"
            >
              <div className="flex items-center gap-2">
                <input defaultChecked className="accent-primary rounded-sm w-3.5 h-3.5" type="checkbox" />
                <span className={`font-mono-sm text-[11px] ${i === 0 ? 'text-on-surface font-semibold' : 'text-on-surface-variant'}`}>
                  {rel.name}
                </span>
              </div>
              <span className="text-primary font-mono-sm text-[11px]">{rel.count}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Filter 3: 4-State Reasoning Filter */}
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between">
          <span className="font-label-caps text-[10px] uppercase text-outline font-semibold">Reasoning State</span>
          <span className="font-mono-sm text-[10px] text-outline">4 States</span>
        </div>
        <div className="flex flex-col gap-1 text-xs">
          {[
            { state: 'OBSERVED', glyph: '✓', count: 7, color: 'text-primary' },
            { state: 'REFUTED_FOR_RUN', glyph: '⊘', count: 2, color: 'text-error' },
            { state: 'POSSIBLE', glyph: '◐', count: 4, color: 'text-tertiary' },
            { state: 'UNKNOWN', glyph: '?', count: 1, color: 'text-outline' },
          ].map((item) => (
            <label
              key={item.state}
              className="flex items-center justify-between px-2 py-1 rounded bg-surface-container cursor-pointer"
            >
              <div className="flex items-center gap-2">
                <input
                  checked={selectedStates[item.state] ?? true}
                  onChange={() => onStateToggle(item.state)}
                  className="accent-primary rounded-sm w-3.5 h-3.5"
                  type="checkbox"
                />
                <span className={`font-mono-sm text-[11px] font-semibold flex items-center gap-1 ${item.color}`}>
                  <span>{item.glyph}</span> {item.state.replace('_FOR_RUN', '')}
                </span>
              </div>
              <span className="px-1.5 py-0.2 rounded bg-surface-container-high text-on-surface font-mono-sm text-[10px] font-bold">
                {item.count}
              </span>
            </label>
          ))}
        </div>
      </div>

      {/* Filter 4: Depth Stepper */}
      <div className="flex flex-col gap-1.5">
        <span className="font-label-caps text-[10px] uppercase text-outline font-semibold">Traversal Depth</span>
        <div className="grid grid-cols-4 gap-1 p-0.5 rounded bg-surface-container-lowest border border-outline-variant/30">
          {[1, 2, 3, 5].map((d) => (
            <button
              key={d}
              className={`py-1 rounded text-center font-mono-sm text-[11px] transition-colors ${
                depth === d
                  ? 'bg-primary text-on-primary font-semibold'
                  : 'text-outline hover:text-on-surface'
              }`}
              onClick={() => onDepthChange(d)}
              type="button"
            >
              {d === 5 ? 'All' : `${d} Hop`}
            </button>
          ))}
        </div>
      </div>

      {/* Anchor Pin Note */}
      <div className="mt-auto bg-surface-container p-2.5 rounded border border-surface-container-highest">
        <div className="flex items-start gap-1.5">
          <span className="material-symbols-outlined text-primary text-[15px] shrink-0 mt-0.5">lock</span>
          <span className="font-mono-sm text-[10px] text-outline leading-tight">
            Base anchor entity <span className="text-on-surface font-semibold underline decoration-primary/40">{anchorName}</span> strictly pinned to graph focal center.
          </span>
        </div>
      </div>
    </aside>
  );
};
