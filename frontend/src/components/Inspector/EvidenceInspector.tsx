import React from 'react';

interface Evidence {
  id: string;
  type: string;
  sourceSystem: string;
  runId?: string;
  granularity: string;
  operator?: string;
  queryFingerprint?: string;
  parserStatus: string;
  ingestionTime?: string;
}

interface Coverage {
  granularity: string;
  diagnostics?: string[];
}

interface EvidenceInspectorProps {
  dependency: {
    source: string;
    target: string;
    sourceId?: string;
    targetId?: string;
  };
  state: 'OBSERVED' | 'REFUTED_FOR_RUN' | 'POSSIBLE' | 'UNKNOWN';
  evidence?: Evidence[];
  coverage?: Coverage;
  temporalContext?: {
    as_of?: string;
    recorded_as_of?: string;
    valid_from?: string;
    valid_to?: string;
    transaction_from?: string;
    transaction_to?: string;
  };
  reasoning?: {
    rule_id?: string;
    engine_version?: string;
    explanation?: string;
    warnings?: string[];
  };
}

const StateColors: Record<string, { bg: string; text: string; icon: string }> = {
  OBSERVED: { bg: 'bg-success/10', text: 'text-success', icon: 'check_circle' },
  REFUTED_FOR_RUN: { bg: 'bg-error/10', text: 'text-error', icon: 'cancel' },
  POSSIBLE: { bg: 'bg-warning/10', text: 'text-warning', icon: 'help' },
  UNKNOWN: { bg: 'bg-outline-variant/10', text: 'text-outline-variant', icon: 'help' },
};

export const EvidenceInspector: React.FC<EvidenceInspectorProps> = ({
  dependency,
  state,
  evidence,
  coverage,
  temporalContext,
  reasoning,
}) => {
  const colors = StateColors[state];

  return (
    <div className="space-y-4">
      {/* Header with State Badge */}
      <div className="bg-surface-container rounded-lg border border-outline-variant p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-mono-sm text-sm font-bold text-on-surface">Dependency</h3>
          <div className={`flex items-center gap-2 px-3 py-1 rounded ${colors.bg}`}>
            <span className={`material-symbols-outlined text-sm ${colors.text}`}>{colors.icon}</span>
            <span className={`font-mono-sm text-xs font-bold ${colors.text}`}>{state}</span>
          </div>
        </div>

        {/* Dependency Path */}
        <div className="flex items-center gap-3 p-3 bg-surface-container-highest rounded border border-outline-variant/50">
          <div className="flex-1 min-w-0">
            <p className="font-mono-sm text-xs text-outline-variant uppercase">Source</p>
            <p className="font-mono-sm text-sm font-bold text-on-surface truncate">{dependency.source}</p>
          </div>
          <span className="material-symbols-outlined text-primary flex-shrink-0">arrow_forward</span>
          <div className="flex-1 min-w-0">
            <p className="font-mono-sm text-xs text-outline-variant uppercase">Target</p>
            <p className="font-mono-sm text-sm font-bold text-on-surface truncate">{dependency.target}</p>
          </div>
        </div>
      </div>

      {/* Evidence Section */}
      {evidence && evidence.length > 0 && (
        <div className="bg-surface-container rounded-lg border border-outline-variant p-4">
          <h3 className="font-mono-sm text-sm font-bold text-on-surface mb-3">Evidence</h3>
          <div className="space-y-2">
            {evidence.map((ev, idx) => (
              <div key={idx} className="p-3 bg-surface-container-highest rounded border border-outline-variant/50">
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="font-mono-sm text-[10px] text-outline-variant uppercase">ID</span>
                    <p className="font-mono-sm text-xs text-on-surface font-mono break-all">{ev.id}</p>
                  </div>
                  <div>
                    <span className="font-mono-sm text-[10px] text-outline-variant uppercase">Type</span>
                    <p className="font-mono-sm text-xs text-on-surface">{ev.type}</p>
                  </div>
                  <div>
                    <span className="font-mono-sm text-[10px] text-outline-variant uppercase">System</span>
                    <p className="font-mono-sm text-xs text-on-surface">{ev.sourceSystem}</p>
                  </div>
                  <div>
                    <span className="font-mono-sm text-[10px] text-outline-variant uppercase">Granularity</span>
                    <p className="font-mono-sm text-xs text-on-surface">{ev.granularity}</p>
                  </div>
                  {ev.runId && (
                    <div>
                      <span className="font-mono-sm text-[10px] text-outline-variant uppercase">Run ID</span>
                      <p className="font-mono-sm text-xs text-on-surface font-mono break-all">{ev.runId}</p>
                    </div>
                  )}
                  {ev.parserStatus && (
                    <div>
                      <span className="font-mono-sm text-[10px] text-outline-variant uppercase">Parser Status</span>
                      <p className="font-mono-sm text-xs text-on-surface">{ev.parserStatus}</p>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Coverage Section */}
      {coverage && (
        <div className="bg-surface-container rounded-lg border border-outline-variant p-4">
          <h3 className="font-mono-sm text-sm font-bold text-on-surface mb-3">Coverage</h3>
          <div className="space-y-2">
            <div className="p-3 bg-surface-container-highest rounded border border-outline-variant/50">
              <div className="grid grid-cols-1 gap-2">
                <div>
                  <span className="font-mono-sm text-[10px] text-outline-variant uppercase">Granularity</span>
                  <p className="font-mono-sm text-xs text-on-surface">{coverage.granularity}</p>
                </div>
                {coverage.diagnostics && coverage.diagnostics.length > 0 && (
                  <div>
                    <span className="font-mono-sm text-[10px] text-outline-variant uppercase">Diagnostics</span>
                    <div className="space-y-1 mt-1">
                      {coverage.diagnostics.map((diag, idx) => (
                        <p key={idx} className="font-mono-sm text-xs text-outline-variant">
                          • {diag}
                        </p>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Temporal Context Section */}
      {temporalContext && (
        <div className="bg-surface-container rounded-lg border border-outline-variant p-4">
          <h3 className="font-mono-sm text-sm font-bold text-on-surface mb-3">Temporal Context</h3>
          <div className="space-y-2">
            <div className="grid grid-cols-2 gap-2 text-xs">
              {temporalContext.as_of && (
                <div className="p-2 bg-surface-container-highest rounded border border-outline-variant/50">
                  <span className="font-mono-sm text-[10px] text-outline-variant uppercase block">as_of</span>
                  <p className="font-mono-sm text-xs text-on-surface font-mono mt-1 break-all">
                    {temporalContext.as_of}
                  </p>
                </div>
              )}
              {temporalContext.recorded_as_of && (
                <div className="p-2 bg-surface-container-highest rounded border border-outline-variant/50">
                  <span className="font-mono-sm text-[10px] text-outline-variant uppercase block">recorded_as_of</span>
                  <p className="font-mono-sm text-xs text-on-surface font-mono mt-1 break-all">
                    {temporalContext.recorded_as_of}
                  </p>
                </div>
              )}
              {temporalContext.valid_from && (
                <div className="p-2 bg-surface-container-highest rounded border border-outline-variant/50">
                  <span className="font-mono-sm text-[10px] text-outline-variant uppercase block">valid_from</span>
                  <p className="font-mono-sm text-xs text-on-surface font-mono mt-1 break-all">
                    {temporalContext.valid_from}
                  </p>
                </div>
              )}
              {temporalContext.valid_to && (
                <div className="p-2 bg-surface-container-highest rounded border border-outline-variant/50">
                  <span className="font-mono-sm text-[10px] text-outline-variant uppercase block">valid_to</span>
                  <p className="font-mono-sm text-xs text-on-surface font-mono mt-1 break-all">
                    {temporalContext.valid_to || 'CURRENT'}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Reasoning Section */}
      {reasoning && (
        <div className="bg-surface-container rounded-lg border border-outline-variant p-4">
          <h3 className="font-mono-sm text-sm font-bold text-on-surface mb-3">Reasoning</h3>
          <div className="space-y-2">
            <div className="p-3 bg-surface-container-highest rounded border border-outline-variant/50">
              <div className="grid grid-cols-1 gap-2">
                {reasoning.rule_id && (
                  <div>
                    <span className="font-mono-sm text-[10px] text-outline-variant uppercase block">Rule ID</span>
                    <p className="font-mono-sm text-xs text-on-surface mt-1">{reasoning.rule_id}</p>
                  </div>
                )}
                {reasoning.engine_version && (
                  <div>
                    <span className="font-mono-sm text-[10px] text-outline-variant uppercase block">Engine Version</span>
                    <p className="font-mono-sm text-xs text-on-surface mt-1">{reasoning.engine_version}</p>
                  </div>
                )}
                {reasoning.explanation && (
                  <div>
                    <span className="font-mono-sm text-[10px] text-outline-variant uppercase block">Explanation</span>
                    <p className="font-mono-sm text-xs text-outline-variant mt-1">{reasoning.explanation}</p>
                  </div>
                )}
                {reasoning.warnings && reasoning.warnings.length > 0 && (
                  <div>
                    <span className="font-mono-sm text-[10px] text-warning uppercase block">Warnings</span>
                    <div className="space-y-1 mt-1">
                      {reasoning.warnings.map((warn, idx) => (
                        <div key={idx} className="flex gap-1 text-xs">
                          <span className="text-warning flex-shrink-0 mt-0.5">⚠</span>
                          <p className="font-mono-sm text-warning-variant">{warn}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
