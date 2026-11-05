/**
 * Catalog payload -> lineage graph mapping.
 *
 * `/api/v1/catalog` is the authoritative source for persisted assets and
 * relationships.  This module is the single place that turns that payload into
 * the node/edge shapes the 2D explorer and the 3D observatory render, so the
 * mapping can be unit tested without a browser and cannot silently drift from
 * what the views draw.
 *
 * Loaded as a classic script before `app.js` (see `appScripts` in auth.js) and
 * exported for Node/Vitest through `module.exports`.
 */
(function (root) {
  'use strict';

  /** Map a catalog asset type onto the three graph roles the views style. */
  function kindOf(raw) {
    const value = String(raw || '').toLowerCase();
    if (/(output|dashboard|semantic|report)/.test(value)) return 'output';
    if (/(transform|model|view|derived)/.test(value)) return 'transform';
    return 'source';
  }

  /** Last identity segment, usable as a node label. */
  function displayName(path) {
    if (path.startsWith('file://') || path.startsWith('directory://')) return path.split('/').pop();
    return path.split('.').pop();
  }

  /**
   * Build graph nodes and edges from one catalog response.
   *
   * Edges are only returned when both endpoints resolve to a loaded asset.
   * Unresolved relationships are counted instead of silently disappearing, so
   * a malformed response is visible in diagnostics rather than looking empty.
   */
  function buildGraph(payload) {
    const source = payload && typeof payload === 'object' ? payload : {};
    const rawAssets = Array.isArray(source.assets) ? source.assets : [];
    const idMap = new Map();

    const assets = rawAssets.map(function (entry, index) {
      const record = entry && typeof entry === 'object' ? entry : {};
      const id = String(record.id || record.qualified_name || 'asset-' + index);
      const path = String(record.qualified_name || record.id || 'unknown');
      idMap.set(String(record.id), id);
      idMap.set(path, id);
      return Object.assign({}, record, {
        id: id,
        name: displayName(path) || path,
        schema: String(record.schema_name || path.split('.').slice(0, -1).join('.') || 'default'),
        kind: kindOf(record.asset_kind || record.asset_type),
        type: String(record.asset_type || record.asset_kind || 'Dataset'),
        rows: '—',
        columns: Number(record.column_count) || 0,
        quality: null,
        owner: String(record.owner_name || 'Unassigned'),
        path: path,
        description: String(record.description || ''),
        is_pii: record.is_pii === undefined ? null : record.is_pii,
        sensitivity_classification: record.sensitivity_classification || null,
        metadata: record.metadata && typeof record.metadata === 'object' ? record.metadata : {},
        source: 'postgresql',
      });
    });

    const resolveId = function (value) {
      return idMap.get(String(value)) || null;
    };

    const rawEdges = Array.isArray(source.edges) ? source.edges : [];
    const edges = [];
    let unresolvedEdges = 0;

    rawEdges.forEach(function (edge) {
      if (!edge || typeof edge !== 'object') {
        unresolvedEdges += 1;
        return;
      }
      const from = resolveId(edge.source_asset_id);
      const to = resolveId(edge.target_asset_id);
      if (!from || !to) {
        unresolvedEdges += 1;
        return;
      }
      edges.push([
        from,
        to,
        String(edge.id || ''),
        String(edge.edge_type || ''),
        edge.metadata && typeof edge.metadata === 'object' ? edge.metadata : {},
        edge.evidence_ref || null,
      ]);
    });

    const counts = source.counts && typeof source.counts === 'object' ? source.counts : {};
    return {
      assets: assets,
      edges: edges,
      counts: {
        assets: assets.length,
        edges: edges.length,
        unresolvedEdges: unresolvedEdges,
        evidence: Number(counts.evidence) || 0,
        rawEvents: Number(counts.raw_events) || 0,
      },
    };
  }

  /**
   * Column index for each node, used by the layered left-to-right graph.
   *
   * ``groupBy='depth'`` (the default) puts a node one column right of its
   * furthest upstream parent, so sources sit on the left and consumers on the
   * right.  ``groupBy='schema'`` instead gives every schema its own column,
   * which makes a wide catalog readable without inventing any relationships.
   * Cycles cannot loop forever: the depth pass is bounded by the node count.
   */
  function assignLayers(assets, edges, options) {
    const nodes = Array.isArray(assets) ? assets : [];
    const links = Array.isArray(edges) ? edges : [];
    const groupBy = options && options.groupBy === 'schema' ? 'schema' : 'depth';
    const layers = {};
    const labels = {};

    if (groupBy === 'schema') {
      const schemas = Array.from(
        new Set(nodes.map(function (asset) { return String(asset.schema || 'default'); }))
      ).sort();
      schemas.forEach(function (schema, index) { labels[index] = schema; });
      nodes.forEach(function (asset) {
        const index = schemas.indexOf(String(asset.schema || 'default'));
        layers[asset.id] = index < 0 ? 0 : index;
      });
      return { layers: layers, labels: labels, groupBy: groupBy };
    }

    nodes.forEach(function (asset) { layers[asset.id] = 0; });
    for (let pass = 0; pass < nodes.length; pass += 1) {
      let moved = false;
      links.forEach(function (edge) {
        const from = edge && edge[0];
        const to = edge && edge[1];
        if (layers[from] === undefined || layers[to] === undefined) return;
        if (layers[to] < layers[from] + 1) {
          layers[to] = layers[from] + 1;
          moved = true;
        }
      });
      if (!moved) break;
    }
    return { layers: layers, labels: labels, groupBy: groupBy };
  }

  root.KairosCatalogGraph = { buildGraph: buildGraph, assignLayers: assignLayers };
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { buildGraph: buildGraph, assignLayers: assignLayers };
  }
})(typeof window !== 'undefined' ? window : globalThis);
