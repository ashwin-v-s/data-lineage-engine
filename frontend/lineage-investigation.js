/* Evidence-neutral graph traversal utilities for interactive investigations. */
(function installLineageInvestigation(root) {
  'use strict';
  root.KairosLineageInvestigation = Object.freeze({
    upstreamTrace(rootId, assets, edges, maxVisited = 1000) {
      const byId = new Map((assets || []).map((asset) => [String(asset.id), asset]));
      const rootKey = String(rootId || '');
      if (!byId.has(rootKey)) return [];
      const queue = [{ id: rootKey, path: [rootKey] }];
      const bestPath = new Map([[rootKey, [rootKey]]]);
      const results = [];
      let visited = 0;
      while (queue.length && visited < maxVisited) {
        const current = queue.shift();
        visited += 1;
        for (const edge of edges || []) {
          const source = String(edge[0] || ''), target = String(edge[1] || '');
          if (target !== current.id || current.path.includes(source) || !byId.has(source)) continue;
          const path = [...current.path, source];
          if (bestPath.has(source)) continue;
          bestPath.set(source, path);
          results.push({ asset: byId.get(source), hops: path.length - 1, path });
          queue.push({ id: source, path });
          if (visited + queue.length >= maxVisited) break;
        }
      }
      return results.sort((left, right) => left.hops - right.hops
        || String(left.asset.path || left.asset.name).localeCompare(String(right.asset.path || right.asset.name)));
    },
  });
})(globalThis);
