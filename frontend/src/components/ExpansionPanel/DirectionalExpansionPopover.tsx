import React, { useState } from 'react';

interface DirectionalExpansionPopoverProps {
  isOpen: boolean;
  nodeName: string;
  onClose: () => void;
  onApply: (options: { direction: 'upstream' | 'downstream' | 'both'; rels: string[] }) => void;
}

export const DirectionalExpansionPopover: React.FC<DirectionalExpansionPopoverProps> = ({
  isOpen,
  nodeName,
  onClose,
  onApply,
}) => {
  const [rels, setRels] = useState<string[]>(['DERIVED_FROM', 'READS']);

  if (!isOpen) return null;

  const toggleRel = (r: string) => {
    setRels((prev) => (prev.includes(r) ? prev.filter((item) => item !== r) : [...prev, r]));
  };

  return (
    <div className="absolute top-24 left-1/3 z-50 w-[260px] bg-surface-container-high/95 backdrop-blur-md rounded-xl border border-primary/50 shadow-2xl p-2.5 flex flex-col gap-2 font-mono-sm">
      <div className="flex items-center justify-between border-b border-surface-container-highest pb-1.5">
        <span className="font-label-caps text-[10px] text-primary uppercase font-bold flex items-center gap-1">
          <span className="material-symbols-outlined text-[14px]">alt_route</span>
          Directional Expansion: {nodeName}
        </span>
        <span className="text-[11px] text-outline cursor-pointer hover:text-on-surface" onClick={onClose}>
          ✕
        </span>
      </div>

      <div className="flex flex-col gap-1">
        <div className="flex items-center justify-between text-[11px] font-semibold text-on-surface py-0.5">
          <span className="flex items-center gap-1 text-primary">
            <span className="material-symbols-outlined text-[13px]">west</span>Expand Upstream
          </span>
          <span className="px-1.5 py-0.2 rounded bg-primary/20 text-primary text-[10px]">4 sources</span>
        </div>
        <div className="flex flex-col gap-1 pl-2 text-[10px] text-outline">
          {['DERIVED_FROM', 'READS', 'WRITES'].map((r) => (
            <label key={r} className="flex items-center justify-between cursor-pointer hover:text-on-surface">
              <div className="flex items-center gap-1.5">
                <input
                  checked={rels.includes(r)}
                  onChange={() => toggleRel(r)}
                  className="accent-primary rounded-sm w-3 h-3"
                  type="checkbox"
                />
                <span>{r}</span>
              </div>
              <span className="text-primary font-bold">{r === 'DERIVED_FROM' ? '2' : '1'}</span>
            </label>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-1 pt-1 border-t border-surface-container-highest">
        <div className="flex items-center justify-between text-[11px] font-semibold text-on-surface py-0.5">
          <span className="flex items-center gap-1 text-on-surface-variant">
            <span className="material-symbols-outlined text-[13px]">east</span>Expand Downstream
          </span>
          <span className="px-1.5 py-0.2 rounded bg-surface-container-highest text-outline text-[10px]">2 targets</span>
        </div>
      </div>

      <button
        className="w-full py-1.5 mt-0.5 bg-primary hover:bg-primary-container text-on-primary hover:text-on-primary-container font-mono-sm text-[11px] font-bold rounded-lg transition-colors flex items-center justify-center gap-1"
        onClick={() => {
          onApply({ direction: 'both', rels });
          onClose();
        }}
        type="button"
      >
        <span className="material-symbols-outlined text-[13px]">unfold_more</span>
        Apply Expansion
      </button>
    </div>
  );
};
