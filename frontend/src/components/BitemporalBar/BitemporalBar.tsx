import React, { useState } from 'react';

interface BitemporalBarProps {
  validAt: string | null;
  knownAsOf: string | null;
  onValidAtChange: (val: string | null) => void;
  onKnownAsOfChange: (val: string | null) => void;
  onResetToLive: () => void;
  isHistorical: boolean;
}

export const BitemporalBar: React.FC<BitemporalBarProps> = ({
  validAt,
  knownAsOf,
  onValidAtChange,
  onKnownAsOfChange,
  onResetToLive,
  isHistorical,
}) => {
  const [showValidAtPicker, setShowValidAtPicker] = useState(false);
  const [showKnownAsOfPicker, setShowKnownAsOfPicker] = useState(false);
  const [tempValidAt, setTempValidAt] = useState(validAt || '2026-08-15T00:00:00Z');
  const [tempKnownAsOf, setTempKnownAsOf] = useState(knownAsOf || '2026-09-23T11:45:00Z');

  const handleValidAtChange = (newVal: string) => {
    setTempValidAt(newVal);
    onValidAtChange(newVal);
    setShowValidAtPicker(false);
  };

  const handleKnownAsOfChange = (newVal: string) => {
    setTempKnownAsOf(newVal);
    onKnownAsOfChange(newVal);
    setShowKnownAsOfPicker(false);
  };

  return (
    <section className="h-10 bg-surface-container px-4 border-b border-surface-container-highest flex items-center justify-between gap-3 shrink-0 z-40 text-xs">
      <div className="flex items-center gap-3 min-w-0 overflow-x-auto py-1">
        {/* Toggle between Historical and Live preset */}
        <span
          className={`px-2.5 py-1 rounded-xl font-label-caps text-[11px] font-bold flex items-center gap-1 shrink-0 shadow-sm cursor-pointer transition-colors ${
            isHistorical
              ? 'bg-tertiary-container/90 text-on-tertiary-container hover:bg-tertiary-container'
              : 'bg-primary-container text-on-primary-container'
          }`}
          onClick={() => {
            if (isHistorical) {
              onResetToLive();
            } else {
              handleValidAtChange('2026-08-15T00:00:00Z');
              handleKnownAsOfChange('2026-09-23T11:45:00Z');
            }
          }}
          title={isHistorical ? 'Click to switch to live mode' : 'Click to jump to historical slice (2026-08-15)'}
        >
          <span className="material-symbols-outlined text-[14px]">
            {isHistorical ? 'history' : 'sensors'}
          </span>
          {isHistorical ? 'HISTORICAL TIME-TRAVEL' : 'LIVE MONITORING'}
        </span>

        {/* Dual Separate Pickers Box */}
        <div className="flex items-center bg-surface-container-lowest/90 backdrop-blur-md rounded-xl border border-tertiary/40 px-3 py-1 gap-2.5 font-mono-sm text-xs shadow-inner">
          {/* 1. Valid at (T_v) — CLICKABLE DATE INPUT */}
          <div
            className="flex items-center gap-1.5 cursor-pointer hover:bg-tertiary-container/20 px-2 py-0.5 rounded transition-colors"
            onClick={() => setShowValidAtPicker(!showValidAtPicker)}
          >
            <span className="material-symbols-outlined text-tertiary text-[13px]">schedule</span>
            <span className="text-tertiary font-label-caps text-[10px] uppercase font-bold">
              Valid at:
            </span>
            <span className="text-tertiary font-bold">
              {validAt ? validAt.substring(0, 10) : 'CURRENT'}
            </span>
            {showValidAtPicker && (
              <input
                type="datetime-local"
                value={tempValidAt.replace('Z', '').substring(0, 16)}
                onChange={(e) => {
                  const val = e.target.value + ':00Z';
                  handleValidAtChange(val);
                }}
                className="ml-2 px-2 py-1 rounded bg-surface text-on-surface text-xs border border-outline-variant font-mono-sm"
                autoFocus
              />
            )}
          </div>

          <span className="text-outline-variant font-mono">|</span>

          {/* 2. Known as of (T_k) — CLICKABLE DATE INPUT */}
          <div
            className="flex items-center gap-1.5 cursor-pointer hover:bg-outline-variant/20 px-2 py-0.5 rounded transition-colors"
            onClick={() => setShowKnownAsOfPicker(!showKnownAsOfPicker)}
          >
            <span className="material-symbols-outlined text-outline text-[13px]">calendar_today</span>
            <span className="text-outline font-label-caps text-[10px] uppercase font-bold">
              Known as of:
            </span>
            <span className="text-on-surface font-semibold">
              {knownAsOf ? knownAsOf.substring(0, 10) : 'LATEST'}
            </span>
            {showKnownAsOfPicker && (
              <input
                type="datetime-local"
                value={tempKnownAsOf.replace('Z', '').substring(0, 16)}
                onChange={(e) => {
                  const val = e.target.value + ':00Z';
                  handleKnownAsOfChange(val);
                }}
                className="ml-2 px-2 py-1 rounded bg-surface text-on-surface text-xs border border-outline-variant font-mono-sm"
                autoFocus
              />
            )}
          </div>
        </div>

        {/* Required Section 19 Historical Banner */}
        {validAt && (
          <div className="hidden xl:flex items-center gap-1.5 text-outline font-mono-sm text-[11px] truncate ml-1">
            <span className="material-symbols-outlined text-tertiary text-[14px] shrink-0">history_toggle_off</span>
            <span className="truncate">
              Temporal slice: <strong className="text-tertiary font-semibold">{validAt.substring(0, 10)}</strong> viewed as of <strong className="text-on-surface font-semibold">{knownAsOf ? knownAsOf.substring(0, 10) : 'latest'}</strong>
            </span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 shrink-0">
        {validAt && (
          <div className="hidden lg:flex items-center gap-1 px-2.5 py-0.5 rounded-xl bg-tertiary-container/20 border border-tertiary/40 text-[10px] font-mono-sm text-tertiary font-semibold">
            <span className="w-1.5 h-1.5 rounded-full bg-tertiary animate-pulse" />
            <span>Temporal filtering active</span>
          </div>
        )}
        <button
          className="flex items-center gap-1 px-3 py-1 rounded-xl bg-surface-container-high hover:bg-surface-container-highest text-on-surface font-mono-sm text-xs transition-colors border border-outline-variant/40 shadow-sm"
          onClick={onResetToLive}
          type="button"
        >
          <span className="material-symbols-outlined text-[14px] text-primary">restart_alt</span>
          <span>Reset to Live</span>
        </button>
      </div>
    </section>
  );
};
