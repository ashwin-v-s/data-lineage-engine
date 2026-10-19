import React, { useState } from 'react';

interface EntityPageProps {
  entityId: string;
  entityName: string;
  entityType: 'TABLE' | 'COLUMN' | 'RUN' | 'JOB';
  schema?: string;
  owner?: string;
  tags?: string[];
  description?: string;
  onBack: () => void;
  onOpenLineage: () => void;
}

export const EntityPage: React.FC<EntityPageProps> = ({
  entityId,
  entityName,
  entityType,
  schema,
  owner,
  tags,
  description,
  onBack,
  onOpenLineage,
}) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'lineage' | 'schema' | 'governance' | 'evidence'>('overview');

  const tabs = [
    { id: 'overview', label: 'Overview', icon: 'info' },
    { id: 'lineage', label: 'Lineage', icon: 'share' },
    { id: 'schema', label: 'Schema', icon: 'table' },
    { id: 'governance', label: 'Governance', icon: 'security' },
    { id: 'evidence', label: 'Evidence', icon: 'fact_check' },
  ] as const;

  return (
    <div className="flex h-screen bg-surface-container-lowest">
      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="bg-surface-container border-b border-outline-variant p-6">
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-4">
              <button
                onClick={onBack}
                className="p-2 hover:bg-surface-container-high rounded transition-colors text-outline hover:text-on-surface"
              >
                <span className="material-symbols-outlined">arrow_back</span>
              </button>
              <div>
                <div className="flex items-center gap-3">
                  <span className="material-symbols-outlined text-2xl text-primary">
                    {entityType === 'TABLE' ? 'table_chart' : 'dns'}
                  </span>
                  <h1 className="font-mono-md text-2xl font-bold text-on-surface">{entityName}</h1>
                  {schema && (
                    <span className="text-xs bg-surface-container-highest px-3 py-1 rounded text-outline">
                      {schema}
                    </span>
                  )}
                </div>
                {description && (
                  <p className="font-mono-sm text-sm text-outline-variant mt-2">{description}</p>
                )}
              </div>
            </div>

            {/* Quick Actions */}
            <div className="flex gap-2">
              <button
                onClick={onOpenLineage}
                className="flex items-center gap-2 px-3 py-2 bg-primary text-on-primary rounded hover:bg-primary-container font-mono-sm text-sm font-bold transition-colors"
              >
                <span className="material-symbols-outlined text-sm">share</span>
                View Lineage
              </button>
            </div>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="bg-surface-container border-b border-outline-variant px-6 flex gap-1 overflow-x-auto">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-3 font-mono-sm text-sm font-semibold transition-colors whitespace-nowrap border-b-2 ${
                activeTab === tab.id
                  ? 'border-primary text-primary'
                  : 'border-transparent text-outline hover:text-on-surface'
              }`}
            >
              <span className="material-symbols-outlined text-sm">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {activeTab === 'overview' && (
            <div className="max-w-4xl space-y-6">
              {/* Metadata Grid */}
              <div className="bg-surface-container rounded-lg border border-outline-variant p-6">
                <h2 className="font-mono-sm text-sm font-bold text-on-surface mb-4">Metadata</h2>
                <div className="grid grid-cols-2 gap-6">
                  <div>
                    <span className="font-mono-sm text-xs text-outline uppercase">Entity ID</span>
                    <p className="font-mono-sm text-sm text-on-surface mt-1 font-mono break-all">{entityId}</p>
                  </div>
                  <div>
                    <span className="font-mono-sm text-xs text-outline uppercase">Entity Type</span>
                    <p className="font-mono-sm text-sm text-on-surface mt-1">{entityType}</p>
                  </div>
                  {owner && (
                    <div>
                      <span className="font-mono-sm text-xs text-outline uppercase">Owner</span>
                      <p className="font-mono-sm text-sm text-on-surface mt-1">{owner}</p>
                    </div>
                  )}
                  {schema && (
                    <div>
                      <span className="font-mono-sm text-xs text-outline uppercase">Schema</span>
                      <p className="font-mono-sm text-sm text-on-surface mt-1">{schema}</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Tags */}
              {tags && tags.length > 0 && (
                <div className="bg-surface-container rounded-lg border border-outline-variant p-6">
                  <h2 className="font-mono-sm text-sm font-bold text-on-surface mb-4">Tags</h2>
                  <div className="flex flex-wrap gap-2">
                    {tags.map(tag => (
                      <span
                        key={tag}
                        className="px-3 py-1 bg-primary/10 text-primary rounded font-mono-sm text-xs"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Description */}
              {description && (
                <div className="bg-surface-container rounded-lg border border-outline-variant p-6">
                  <h2 className="font-mono-sm text-sm font-bold text-on-surface mb-4">Description</h2>
                  <p className="font-mono-sm text-sm text-outline-variant">{description}</p>
                </div>
              )}
            </div>
          )}

          {activeTab === 'lineage' && (
            <div className="max-w-4xl bg-surface-container rounded-lg border border-outline-variant p-6 h-96 flex items-center justify-center">
              <div className="text-center text-outline-variant">
                <span className="material-symbols-outlined text-5xl opacity-30">share</span>
                <p className="font-mono-sm text-sm mt-2">Click "View Lineage" to see the full lineage graph</p>
              </div>
            </div>
          )}

          {activeTab === 'schema' && (
            <div className="max-w-4xl bg-surface-container rounded-lg border border-outline-variant p-6">
              <h2 className="font-mono-sm text-sm font-bold text-on-surface mb-4">Schema Details</h2>
              <p className="font-mono-sm text-sm text-outline-variant">Schema information coming soon...</p>
            </div>
          )}

          {activeTab === 'governance' && (
            <div className="max-w-4xl space-y-6">
              <div className="bg-surface-container rounded-lg border border-outline-variant p-6">
                <h2 className="font-mono-sm text-sm font-bold text-on-surface mb-4">Governance</h2>
                {owner ? (
                  <div>
                    <span className="font-mono-sm text-xs text-outline uppercase">Owner</span>
                    <p className="font-mono-sm text-sm text-on-surface mt-1">{owner}</p>
                  </div>
                ) : (
                  <p className="font-mono-sm text-sm text-outline-variant">No ownership information</p>
                )}
              </div>

              <div className="bg-surface-container rounded-lg border border-outline-variant p-6">
                <h2 className="font-mono-sm text-sm font-bold text-on-surface mb-4">Certifications</h2>
                <p className="font-mono-sm text-sm text-outline-variant">No certifications yet</p>
              </div>
            </div>
          )}

          {activeTab === 'evidence' && (
            <div className="max-w-4xl bg-surface-container rounded-lg border border-outline-variant p-6">
              <h2 className="font-mono-sm text-sm font-bold text-on-surface mb-4">Evidence</h2>
              <div className="space-y-4">
                <div className="p-4 bg-surface-container-highest rounded border border-outline-variant">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono-sm text-xs font-bold text-primary uppercase">OBSERVED</span>
                    <span className="text-xs text-outline">3 evidence records</span>
                  </div>
                  <p className="font-mono-sm text-sm text-outline-variant">
                    Evidence supporting this entity's lineage relationships
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Right Sidebar - Quick Info (optional) */}
      <div className="w-80 bg-surface-container border-l border-outline-variant p-6 overflow-y-auto hidden lg:block">
        <h2 className="font-mono-sm text-sm font-bold text-on-surface mb-4">Quick Info</h2>

        <div className="space-y-4">
          {/* Related Assets */}
          <div>
            <h3 className="font-mono-sm text-xs font-semibold text-outline uppercase mb-2">Related Assets</h3>
            <div className="space-y-2">
              <div className="p-2 bg-surface-container-highest rounded hover:bg-surface-container-highest/80 cursor-pointer transition-colors">
                <p className="font-mono-sm text-xs text-on-surface">orders_fact</p>
                <p className="font-mono-sm text-[10px] text-outline-variant">Downstream</p>
              </div>
            </div>
          </div>

          {/* Statistics */}
          <div className="pt-4 border-t border-outline-variant">
            <h3 className="font-mono-sm text-xs font-semibold text-outline uppercase mb-3">Statistics</h3>
            <div className="grid grid-cols-2 gap-2">
              <div className="p-2 bg-surface-container-highest rounded">
                <p className="font-mono-sm text-xs text-outline-variant">Upstream</p>
                <p className="font-mono-sm text-lg font-bold text-primary">2</p>
              </div>
              <div className="p-2 bg-surface-container-highest rounded">
                <p className="font-mono-sm text-xs text-outline-variant">Downstream</p>
                <p className="font-mono-sm text-lg font-bold text-primary">1</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
