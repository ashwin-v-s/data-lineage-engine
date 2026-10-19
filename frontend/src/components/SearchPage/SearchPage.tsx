import React, { useState, useMemo } from 'react';
import { useSearchQuery } from '../../api/queries';

interface SearchResult {
  id: string;
  label: string;
  type: 'TABLE' | 'COLUMN' | 'RUN' | 'EVIDENCE' | 'JOB';
  schema?: string;
  owner?: string;
  tags?: string[];
  description?: string;
  created?: string;
}

interface SearchPageProps {
  onSelectEntity: (id: string, type: string) => void;
}

export const SearchPage: React.FC<SearchPageProps> = ({ onSelectEntity }) => {
  const [query, setQuery] = useState('');
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [selectedSchema, setSelectedSchema] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<'relevance' | 'name' | 'updated'>('relevance');

  const { data: searchData, isLoading } = useSearchQuery(query);
  const results = (searchData?.results || []) as SearchResult[];

  // Filter results by type and schema
  const filteredResults = useMemo(() => {
    return results.filter(r => {
      if (selectedType && r.type !== selectedType) return false;
      if (selectedSchema && r.schema !== selectedSchema) return false;
      return true;
    });
  }, [results, selectedType, selectedSchema]);

  // Get unique schemas from results
  const schemas = useMemo(() => {
    return Array.from(new Set(results.map(r => r.schema).filter(Boolean))) as string[];
  }, [results]);

  // Get unique types from results
  const types = useMemo(() => {
    return Array.from(new Set(results.map(r => r.type))) as string[];
  }, [results]);

  // Group results by type
  const groupedResults = useMemo(() => {
    const grouped: Record<string, SearchResult[]> = {};
    filteredResults.forEach(r => {
      if (!grouped[r.type]) grouped[r.type] = [];
      grouped[r.type].push(r);
    });
    return grouped;
  }, [filteredResults]);

  return (
    <div className="flex h-screen bg-surface-container-lowest">
      {/* Left Sidebar - Filters */}
      <div className="w-64 bg-surface-container border-r border-outline-variant p-4 overflow-y-auto">
        <h2 className="font-mono-sm text-sm font-bold text-on-surface mb-4">Filters</h2>

        {/* Type Filter */}
        <div className="mb-6">
          <h3 className="font-mono-sm text-xs font-semibold text-outline mb-2 uppercase">Type</h3>
          <div className="space-y-1">
            <button
              onClick={() => setSelectedType(null)}
              className={`w-full text-left px-2 py-1 rounded font-mono-sm text-xs transition-colors ${
                selectedType === null
                  ? 'bg-primary text-on-primary'
                  : 'text-outline hover:text-on-surface hover:bg-surface-container-high'
              }`}
            >
              All ({results.length})
            </button>
            {types.map(type => {
              const count = results.filter(r => r.type === type).length;
              return (
                <button
                  key={type}
                  onClick={() => setSelectedType(type)}
                  className={`w-full text-left px-2 py-1 rounded font-mono-sm text-xs transition-colors ${
                    selectedType === type
                      ? 'bg-primary text-on-primary'
                      : 'text-outline hover:text-on-surface hover:bg-surface-container-high'
                  }`}
                >
                  {type} ({count})
                </button>
              );
            })}
          </div>
        </div>

        {/* Schema Filter */}
        <div className="mb-6">
          <h3 className="font-mono-sm text-xs font-semibold text-outline mb-2 uppercase">Schema</h3>
          <div className="space-y-1">
            <button
              onClick={() => setSelectedSchema(null)}
              className={`w-full text-left px-2 py-1 rounded font-mono-sm text-xs transition-colors ${
                selectedSchema === null
                  ? 'bg-primary text-on-primary'
                  : 'text-outline hover:text-on-surface hover:bg-surface-container-high'
              }`}
            >
              All
            </button>
            {schemas.map(schema => {
              const count = results.filter(r => r.schema === schema).length;
              return (
                <button
                  key={schema}
                  onClick={() => setSelectedSchema(schema)}
                  className={`w-full text-left px-2 py-1 rounded font-mono-sm text-xs transition-colors ${
                    selectedSchema === schema
                      ? 'bg-primary text-on-primary'
                      : 'text-outline hover:text-on-surface hover:bg-surface-container-high'
                  }`}
                >
                  <span className="truncate">{schema}</span>
                  <span className="ml-auto text-[10px]">({count})</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Sort Options */}
        <div>
          <h3 className="font-mono-sm text-xs font-semibold text-outline mb-2 uppercase">Sort</h3>
          <div className="space-y-1">
            {(['relevance', 'name', 'updated'] as const).map(option => (
              <button
                key={option}
                onClick={() => setSortBy(option)}
                className={`w-full text-left px-2 py-1 rounded font-mono-sm text-xs transition-colors capitalize ${
                  sortBy === option
                    ? 'bg-primary text-on-primary'
                    : 'text-outline hover:text-on-surface hover:bg-surface-container-high'
                }`}
              >
                {option}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Search Header */}
        <div className="bg-surface-container border-b border-outline-variant p-6">
          <h1 className="font-mono-md text-lg font-bold text-on-surface mb-4">Search Assets</h1>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Search tables, columns, runs, evidence..."
              value={query}
              onChange={e => setQuery(e.target.value)}
              className="flex-1 px-4 py-2 rounded bg-surface-container-highest border border-outline-variant text-on-surface placeholder:text-outline-variant font-mono-sm text-sm focus:outline-none focus:border-primary"
            />
            <button className="px-4 py-2 bg-primary text-on-primary rounded hover:bg-primary-container font-mono-sm text-sm font-bold transition-colors">
              Search
            </button>
          </div>
        </div>

        {/* Results Area */}
        <div className="flex-1 overflow-y-auto p-6">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-outline">
              <span className="material-symbols-outlined text-5xl opacity-30 animate-spin">
                hourglass_empty
              </span>
              <p className="font-mono-sm text-sm">Searching...</p>
            </div>
          ) : filteredResults.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-outline-variant">
              <span className="material-symbols-outlined text-5xl opacity-30">search_off</span>
              <div className="text-center">
                <p className="font-mono-sm text-sm font-semibold mb-1">No results found</p>
                <p className="font-mono-sm text-xs opacity-70">
                  Try different search terms or filters
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {Object.entries(groupedResults).map(([type, items]) => (
                <div key={type}>
                  <h2 className="font-mono-sm text-xs font-bold text-outline uppercase tracking-wider mb-2">
                    {type} ({items.length})
                  </h2>
                  <div className="space-y-2">
                    {items.map(result => (
                      <button
                        key={result.id}
                        onClick={() => onSelectEntity(result.id, result.type)}
                        className="w-full text-left p-3 rounded bg-surface-container hover:bg-surface-container-high border border-outline-variant hover:border-primary transition-colors group"
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="material-symbols-outlined text-sm text-primary flex-shrink-0">
                                {result.type === 'TABLE' ? 'table_chart' : 'dns'}
                              </span>
                              <h3 className="font-mono-sm text-sm font-bold text-on-surface truncate">
                                {result.label}
                              </h3>
                              {result.schema && (
                                <span className="text-[10px] text-outline bg-surface-container-highest px-1.5 py-0.5 rounded flex-shrink-0">
                                  {result.schema}
                                </span>
                              )}
                            </div>
                            {result.description && (
                              <p className="font-mono-sm text-xs text-outline-variant mt-1 line-clamp-2">
                                {result.description}
                              </p>
                            )}
                            {result.tags && result.tags.length > 0 && (
                              <div className="flex gap-1 mt-2 flex-wrap">
                                {result.tags.slice(0, 3).map(tag => (
                                  <span
                                    key={tag}
                                    className="text-[10px] bg-primary/10 text-primary px-2 py-1 rounded"
                                  >
                                    {tag}
                                  </span>
                                ))}
                                {result.tags.length > 3 && (
                                  <span className="text-[10px] text-outline px-2 py-1">
                                    +{result.tags.length - 3}
                                  </span>
                                )}
                              </div>
                            )}
                          </div>
                          <span className="material-symbols-outlined text-outline-variant group-hover:text-primary transition-colors flex-shrink-0 ml-2">
                            arrow_forward
                          </span>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
