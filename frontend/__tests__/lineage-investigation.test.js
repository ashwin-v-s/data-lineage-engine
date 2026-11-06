import { describe, expect, it } from 'vitest';
import '../lineage-investigation.js';

describe('upstream root-cause traversal', () => {
  it('returns shortest recorded upstream paths and tolerates cycles', () => {
    const assets = [
      { id: 'symptom', path: 'mart.orders' },
      { id: 'model', path: 'staging.orders' },
      { id: 'source', path: 'raw.orders' },
    ];
    const edges = [['source', 'model'], ['model', 'symptom'], ['symptom', 'source']];
    const trace = globalThis.KairosLineageInvestigation.upstreamTrace('symptom', assets, edges);
    expect(trace.map((entry) => [entry.asset.id, entry.hops])).toEqual([
      ['model', 1], ['source', 2],
    ]);
    expect(trace[1].path).toEqual(['symptom', 'model', 'source']);
  });

  it('returns no inferred path for an unknown anchor', () => {
    expect(globalThis.KairosLineageInvestigation.upstreamTrace('missing', [], [])).toEqual([]);
  });
});
