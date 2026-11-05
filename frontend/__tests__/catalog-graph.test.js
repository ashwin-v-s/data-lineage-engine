import { describe, expect, it } from 'vitest';

import '../catalog-graph.js';

const { buildGraph, assignLayers } = globalThis.KairosCatalogGraph;

/** A catalog response shaped like the real `/api/v1/catalog` payload. */
function catalogResponse(overrides = {}) {
  return {
    ok: true,
    assets: [
      {
        id: '593f92b3-a4ac-4172-91d0-a60abe28eafd',
        source_system: 'upload',
        namespace: 'warehouse.raw',
        database_name: '',
        schema_name: 'warehouse.raw',
        name: 'orders',
        asset_type: 'TABLE',
        qualified_name: 'warehouse.raw.orders',
        column_count: 3,
        metadata: { source_system: 'upload' },
        owner_name: null,
      },
      {
        id: '6adc66d2-7583-40a9-a030-b18f83732bec',
        source_system: 'upload',
        namespace: 'analytics',
        database_name: '',
        schema_name: 'analytics',
        name: 'orders_model',
        asset_type: 'MODEL',
        qualified_name: 'analytics.orders_model',
        column_count: 0,
        metadata: { source_system: 'upload' },
        owner_name: null,
      },
    ],
    edges: [
      {
        id: 'edge-1',
        source_asset_id: '593f92b3-a4ac-4172-91d0-a60abe28eafd',
        target_asset_id: '6adc66d2-7583-40a9-a030-b18f83732bec',
        edge_type: 'DATASET',
        evidence_ref: 'evidence-1',
        metadata: { provenance: 'upload' },
      },
    ],
    counts: { assets: 2, edges: 1, evidence: 1, raw_events: 1 },
    ...overrides,
  };
}

describe('buildGraph', () => {
  it('maps persisted assets to graph nodes with their qualified names', () => {
    const graph = buildGraph(catalogResponse());

    expect(graph.assets.map((asset) => asset.path)).toEqual([
      'warehouse.raw.orders',
      'analytics.orders_model',
    ]);
    expect(graph.assets.map((asset) => asset.name)).toEqual(['orders', 'orders_model']);
    expect(graph.assets.map((asset) => asset.schema)).toEqual(['warehouse.raw', 'analytics']);
    expect(graph.assets[0].kind).toBe('source');
    expect(graph.assets[1].kind).toBe('transform');
    expect(graph.assets[0].owner).toBe('Unassigned');
    expect(graph.assets[0].source).toBe('postgresql');
  });

  it('resolves the relationship endpoints onto the loaded node ids', () => {
    const graph = buildGraph(catalogResponse());

    expect(graph.counts.edges).toBe(1);
    expect(graph.counts.unresolvedEdges).toBe(0);
    const [from, to, id, type] = graph.edges[0];
    expect(from).toBe(graph.assets[0].id);
    expect(to).toBe(graph.assets[1].id);
    expect(id).toBe('edge-1');
    expect(type).toBe('DATASET');
  });

  it('counts relationships whose endpoints are not in the payload', () => {
    const payload = catalogResponse({
      edges: [
        ...catalogResponse().edges,
        { id: 'edge-2', source_asset_id: 'missing', target_asset_id: 'also-missing' },
      ],
      counts: { assets: 2, edges: 2, evidence: 1, raw_events: 1 },
    });

    const graph = buildGraph(payload);

    expect(graph.edges).toHaveLength(1);
    expect(graph.counts.unresolvedEdges).toBe(1);
  });

  it('carries the persisted counts through for the source banner', () => {
    const graph = buildGraph(catalogResponse());

    expect(graph.counts).toMatchObject({ assets: 2, edges: 1, evidence: 1, rawEvents: 1 });
  });

  it('is safe for empty or malformed payloads', () => {
    expect(buildGraph(null)).toEqual({
      assets: [],
      edges: [],
      counts: { assets: 0, edges: 0, unresolvedEdges: 0, evidence: 0, rawEvents: 0 },
    });
    expect(buildGraph({ assets: 'nope', edges: 'nope' }).assets).toEqual([]);
    expect(buildGraph('not-an-object').edges).toEqual([]);
  });

  it('falls back to the qualified name when an asset has no id', () => {
    const graph = buildGraph({
      assets: [{ qualified_name: 'warehouse.raw.orders', asset_type: 'TABLE' }],
      edges: [],
    });

    expect(graph.assets[0].id).toBe('warehouse.raw.orders');
    expect(graph.assets[0].name).toBe('orders');
  });
});

describe('assignLayers', () => {
  const graph = buildGraph(catalogResponse());

  it('places each asset one column right of its upstream parent', () => {
    const layout = assignLayers(graph.assets, graph.edges, { groupBy: 'depth' });

    expect(layout.groupBy).toBe('depth');
    expect(layout.layers[graph.assets[0].id]).toBe(0);
    expect(layout.layers[graph.assets[1].id]).toBe(1);
  });

  it('gives each schema its own column with a readable header when grouped', () => {
    const layout = assignLayers(graph.assets, graph.edges, { groupBy: 'schema' });

    expect(layout.groupBy).toBe('schema');
    // Columns are alphabetical by schema, independent of the relationship order.
    expect(layout.layers[graph.assets[0].id]).toBe(1);
    expect(layout.layers[graph.assets[1].id]).toBe(0);
    expect(layout.labels).toEqual({ 0: 'analytics', 1: 'warehouse.raw' });
  });

  it('terminates on cyclic relationships instead of looping forever', () => {
    const cyclic = [
      { id: 'a', schema: 's' },
      { id: 'b', schema: 's' },
    ];
    const layout = assignLayers(cyclic, [['a', 'b'], ['b', 'a']], { groupBy: 'depth' });

    expect(Number.isFinite(layout.layers.a)).toBe(true);
    expect(Number.isFinite(layout.layers.b)).toBe(true);
  });

  it('is safe for empty input and unknown nodes', () => {
    expect(assignLayers([], [], {}).layers).toEqual({});
    expect(assignLayers([{ id: 'a', schema: 's' }], [['a', 'missing']], {}).layers).toEqual({ a: 0 });
  });
});
