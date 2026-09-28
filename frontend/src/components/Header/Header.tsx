import React, { useState, useEffect, useRef } from 'react';
import { api } from '../../api/client';
import { EntitySummary } from '../../api/types';

interface HeaderProps {
  density: 'investigator' | 'research';
  onDensityChange: (mode: 'investigator' | 'research') => void;
  runId: string;
  benchmarkMode: boolean;
  onBenchmarkToggle: () => void;
  onSelectEntity: (entityId: string) => void;
}

export const Header: React.FC<HeaderProps> = ({
  density,
  onDensityChange,
  runId,
  benchmarkMode,
  onBenchmarkToggle,
  onSelectEntity,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<EntitySummary[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      setDropdownOpen(false);
      return;
    }
    const timer = setTimeout(async () => {
      setIsSearching(true);
      try {
        const res = await api.search(searchQuery.trim());
        setSearchResults(res.results || []);
        setDropdownOpen(true);
      } catch (err) {
        console.error('Search failed:', err);
      } finally {
        setIsSearching(false);
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Click outside to close dropdown
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <>
      {/* BENCHMARK HAZARD BANNER (Section 13) */}
      {benchmarkMode && (
        <div className="w-full bg-secondary-container/90 text-on-secondary-container border-b border-secondary/40 px-4 py-2 flex items-center justify-between text-xs font-mono-sm z-50 backdrop-blur-md">
          <div className="flex items-center gap-2 min-w-0">
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-secondary opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-secondary"></span>
            </span>
            <span className="font-bold tracking-wider uppercase text-secondary">
              Benchmark Evaluation Mode Active
            </span>
            <span className="text-outline-variant">—</span>
            <span className="truncate text-on-secondary-container/90">
              Ground Truth Oracle (<code className="text-secondary font-bold">PROPAGATED</code> /{' '}
              <code className="text-outline font-bold">NOT_PROPAGATED</code>) exposed strictly for{' '}
              <span className="font-mono font-bold text-on-secondary">{runId}</span>. Strict leakage boundary enforced.
            </span>
          </div>
          <div className="flex items-center gap-2 shrink-0 ml-3">
            <span className="px-2 py-0.5 rounded-xl bg-secondary/20 border border-secondary/30 text-[10px] font-semibold text-secondary uppercase">
              Oracle Unlocked
            </span>
            <button
              className="text-on-secondary-container hover:text-white p-1 rounded-xl hover:bg-secondary/20 transition-colors"
              onClick={onBenchmarkToggle}
              title="Close Benchmark Mode"
            >
              <span className="material-symbols-outlined text-[16px]">close</span>
            </button>
          </div>
        </div>
      )}

      {/* PRIMARY HEADER */}
      <header className="h-14 bg-surface-container-low border-b border-surface-container-highest px-4 flex items-center justify-between gap-4 shrink-0 z-50">
        {/* Brand / Engine */}
        <div className="flex items-center gap-3 shrink-0">
          <div className="flex items-center gap-2 cursor-pointer" onClick={() => onSelectEntity('orders_fact')}>
            <span className="material-symbols-outlined text-primary text-[22px]">hub</span>
            <span className="font-headline-sm text-base font-bold tracking-wider text-on-surface uppercase">
              Kairos
            </span>
          </div>
          <span className="px-2 py-0.5 rounded bg-surface-container-highest text-outline font-mono-sm text-[11px] uppercase tracking-wider">
            v1.0-engine
          </span>
        </div>

        {/* Global Search Input with API debouncing */}
        <div className="flex-1 max-w-xl relative" ref={dropdownRef}>
          <div className="relative flex items-center w-full h-8 px-3 bg-surface-container rounded border border-outline-variant/40 focus-within:border-primary transition-colors">
            <span className="material-symbols-outlined text-outline text-[16px] mr-2">search</span>
            <input
              className="w-full bg-transparent border-0 outline-none text-on-surface placeholder:text-outline font-mono-sm text-xs"
              placeholder="Search entities (e.g. orders_fact, customer_id, daily_pipeline)..."
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onFocus={() => searchResults.length > 0 && setDropdownOpen(true)}
            />
            {isSearching && (
              <span className="w-3 h-3 border-2 border-primary border-t-transparent rounded-full animate-spin mr-2"></span>
            )}
            <div className="flex items-center gap-1.5 shrink-0 ml-2">
              <span className="px-1.5 py-0.5 rounded bg-surface-container-high text-outline font-label-caps text-[10px]">
                DATASET
              </span>
              <span className="px-1.5 py-0.5 rounded bg-surface-container-high text-outline font-label-caps text-[10px]">
                COLUMN
              </span>
              <kbd className="px-1.5 py-0.5 rounded bg-surface-container-highest text-on-surface-variant font-mono-sm text-[11px]">
                ⌘K
              </kbd>
            </div>
          </div>

          {/* Autocomplete Dropdown */}
          {dropdownOpen && searchResults.length > 0 && (
            <div className="absolute top-10 left-0 right-0 bg-surface-container-high/95 backdrop-blur-md rounded border border-outline-variant/50 shadow-2xl p-1.5 z-50 max-h-72 overflow-y-auto">
              {searchResults.map((item) => (
                <div
                  key={item.id}
                  className="flex items-center justify-between p-2 rounded hover:bg-surface-container-highest cursor-pointer transition-colors"
                  onClick={() => {
                    onSelectEntity(item.id || item.name);
                    setDropdownOpen(false);
                    setSearchQuery('');
                  }}
                >
                  <div className="flex flex-col">
                    <span className="font-mono-sm text-xs font-bold text-on-surface">{item.display_name || item.name}</span>
                    <span className="font-mono-sm text-[10px] text-outline">
                      {item.namespace} • {item.entity_type} {item.column_count ? `(${item.column_count} cols)` : ''}
                    </span>
                  </div>
                  <span className="px-1.5 py-0.5 rounded bg-surface-container-lowest text-primary font-label-caps text-[10px]">
                    SELECT
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right Controls: View Density + Mode Controls */}
        <div className="flex items-center gap-3 shrink-0">
          {/* VIEW DENSITY TOGGLE [Investigator (default) | Research] */}
          <div
            aria-label="View Density"
            className="flex items-center bg-surface-container-lowest p-0.5 rounded border border-outline-variant/50"
            role="group"
          >
            <button
              className={`flex items-center gap-1 px-2.5 py-1 rounded text-xs font-mono-sm font-semibold transition-all ${
                density === 'investigator'
                  ? 'bg-primary-container text-on-primary-container shadow-sm'
                  : 'text-outline hover:text-on-surface'
              }`}
              onClick={() => onDensityChange('investigator')}
              title="Streamlined high-signal view for incidents and verification"
            >
              <span className="material-symbols-outlined text-[14px]">visibility</span>
              <span>Investigator</span>
            </button>
            <button
              className={`flex items-center gap-1 px-2.5 py-1 rounded text-xs font-mono-sm font-medium transition-all ${
                density === 'research'
                  ? 'bg-primary-container text-on-primary-container shadow-sm font-semibold'
                  : 'text-outline hover:text-on-surface'
              }`}
              onClick={() => onDensityChange('research')}
              title="Full forensic vector exposure with query fingerprints and raw derivations"
            >
              <span className="material-symbols-outlined text-[14px]">biotech</span>
              <span>Research</span>
            </button>
          </div>

          {/* Scoped Run Indicator */}
          <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-container text-on-surface font-mono-sm text-xs border border-surface-container-highest">
            <span className="material-symbols-outlined text-outline text-[16px]">terminal</span>
            <span className="text-outline">Run:</span>
            <span className="text-primary font-medium">{runId}</span>
          </div>

          {/* Benchmark Evaluation Mode Toggle */}
          <button
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded font-mono-sm text-xs font-medium transition-colors border shadow-sm ${
              benchmarkMode
                ? 'bg-secondary text-on-secondary border-secondary'
                : 'bg-secondary-container text-on-secondary-container hover:bg-secondary hover:text-on-secondary border-secondary/40'
            }`}
            onClick={onBenchmarkToggle}
            type="button"
          >
            <span className="material-symbols-outlined text-[16px]">science</span>
            <span>Benchmark Evaluation Mode</span>
            <span className="w-2 h-2 rounded-full bg-secondary ml-0.5 animate-pulse" />
          </button>

          {/* Invariant status */}
          <button
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-surface-container border border-outline-variant/30 text-outline hover:text-primary transition-colors text-xs font-mono-sm"
            title="Invariant T_k ≥ T_v (Strict) — 0 assertions violated"
            type="button"
          >
            <span className="material-symbols-outlined text-primary text-[14px]">verified_user</span>
            <span className="hidden xl:inline text-[11px] text-outline">T_k ≥ T_v</span>
            <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
          </button>

          <div className="w-7 h-7 rounded-full bg-primary flex items-center justify-center shrink-0">
            <span className="material-symbols-outlined text-on-primary text-[16px]">person</span>
          </div>
        </div>
      </header>
    </>
  );
};
