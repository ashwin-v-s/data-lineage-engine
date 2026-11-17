import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it, vi } from 'vitest';

import '../lineage-edge-inspector.js';

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');

const { describeEdge, coverageRows, createEdgeSelection, SELECTED_CLASS, NOT_RECORDED } =
  globalThis.KairosEdgeInspector;

/**
 * A minimal canvas-element stand-in: the inspector binding only needs
 * `addEventListener`, `classList` and `dataset`, so the interaction contract can
 * be exercised without a browser DOM (the suite runs in the node environment).
 */
function fakeEdge(name) {
  const listeners = new Map();
  const classes = new Set();
  const element = {
    name,
    dataset: {},
    classList: {
      add: (value) => classes.add(value),
      remove: (value) => classes.delete(value),
      contains: (value) => classes.has(value),
    },
    addEventListener: (type, handler) => {
      if (!listeners.has(type)) listeners.set(type, []);
      listeners.get(type).push(handler);
    },
    /** Fire a listener and report whether it stopped propagation. */
    fire(type, event = {}) {
      const stopped = { propagation: false, defaultPrevented: false };
      const payload = {
        key: undefined,
        preventDefault: () => {
          stopped.defaultPrevented = true;
        },
        stopPropagation: () => {
          stopped.propagation = true;
        },
        ...event,
      };
      (listeners.get(type) || []).forEach((handler) => handler(payload));
      return stopped;
    },
  };
  return element;
}

/** The stored evidence aggregate the edge endpoint returns for this demo edge. */
const observedAggregate = {
  state: 'OBSERVED',
  coverage: 'COMPLETE',
  state_reason: 'A runtime event observed this relationship directly.',
  coverage_basis: ['OPENLINEAGE_RUNTIME'],
  coverage_scope: 'DATASET',
  evidence_count: 1,
  run_count: 1,
};

const possibleAggregate = {
  state: 'POSSIBLE',
  coverage: 'PARTIAL',
  state_reason: 'A recorded transformation implies the relationship but no run observed it.',
  coverage_basis: ['SQL'],
  coverage_scope: 'DATASET',
  evidence_count: 1,
  run_count: 0,
};

const runtimeCoverage = {
  scope: 'DATASET',
  run_covered: true,
  operator_covered: false,
  source_dataset_covered: true,
  target_dataset_covered: true,
  branches_covered: false,
  coverage_mode: 'runtime',
  parser_status: 'PARTIAL',
};

const relationship = {
  edgeId: '90b4fe0a-3980-47f5-836c-5b02e23691c8',
  edgeType: 'DATASET',
  mappingType: 'RUNTIME_POSITIVE',
  sourcePath: 'analytics.public.orders',
  targetPath: 'analytics.public.revenue_daily',
  validFrom: '2026-11-15T10:15:00+00:00',
  recordedFrom: '2026-11-17T15:42:44.362139+00:00',
};

const row = (detail, label) => detail.rows.find((entry) => entry.label === label);

describe('edge inspector model', () => {
  it('describes an OBSERVED relationship from stored evidence', () => {
    const detail = describeEdge({ ...relationship, aggregate: observedAggregate });

    expect(detail.title).toBe('Lineage relationship evidence');
    expect(detail.state).toBe('OBSERVED');
    expect(detail.coverage).toBe('COMPLETE');
    expect(detail.evidenceCount).toBe(1);
    expect(detail.runCount).toBe(1);
  });

  it('describes a POSSIBLE relationship without promoting it', () => {
    const detail = describeEdge({ ...relationship, aggregate: possibleAggregate });

    expect(detail.state).toBe('POSSIBLE');
    expect(detail.coverage).toBe('PARTIAL');
    expect(detail.state).not.toBe('OBSERVED');
  });

  it('names the exact source and target of the clicked edge', () => {
    const detail = describeEdge({ ...relationship, aggregate: observedAggregate });

    expect(detail.heading).toBe('analytics.public.orders → analytics.public.revenue_daily');
    expect(row(detail, 'Source dataset').value).toBe('analytics.public.orders');
    expect(row(detail, 'Target dataset').value).toBe('analytics.public.revenue_daily');
    expect(row(detail, 'Relationship type').value).toBe('DATASET');
    expect(row(detail, 'Granularity').value).toBe('DATASET');
    expect(row(detail, 'Mapping type').value).toBe('RUNTIME_POSITIVE');
    expect(row(detail, 'Edge ID').value).toBe('90b4fe0a-3980-47f5-836c-5b02e23691c8');
  });

  it('reports the stored coverage facts in readable form', () => {
    const rows = coverageRows(runtimeCoverage);
    const value = (label) => rows.find((entry) => entry.label === label).value;

    expect(value('Coverage mode')).toBe('runtime');
    expect(value('Run covered')).toBe('Covered');
    expect(value('Source dataset covered')).toBe('Covered');
    expect(value('Target dataset covered')).toBe('Covered');
    expect(value('Operator covered')).toBe('Not covered');
    expect(value('Parser status')).toBe('PARTIAL');
    expect(coverageRows(null)).toEqual([]);
  });

  it('marks unavailable fields instead of inventing them', () => {
    const detail = describeEdge({
      edgeId: 'edge-without-metadata',
      edgeType: 'DATASET',
      sourcePath: 'analytics.public.orders',
      targetPath: 'analytics.public.revenue_daily',
      aggregate: observedAggregate,
    });

    expect(row(detail, 'Mapping type')).toEqual({
      label: 'Mapping type',
      value: NOT_RECORDED,
      known: false,
    });
    expect(row(detail, 'Valid from').value).toBe(NOT_RECORDED);
    expect(row(detail, 'Recorded from').value).toBe(NOT_RECORDED);
    // Granularity falls back to the edge type, which is the same stored scope.
    expect(row(detail, 'Granularity').value).toBe('DATASET');
    expect(detail.state).toBe('OBSERVED');
  });

  it('keeps a missing aggregate as an unknown state, not an observation', () => {
    const detail = describeEdge({ ...relationship, aggregate: null });

    expect(detail.state).toBe(NOT_RECORDED);
    expect(detail.coverage).toBe(NOT_RECORDED);
  });
});

describe('edge selection on the canvas', () => {
  it('opens the inspector for an OBSERVED edge and marks it selected', () => {
    const observed = fakeEdge('observed');
    const onSelect = vi.fn();
    const selection = createEdgeSelection({ onSelect });

    selection.bind([observed], () => onSelect(describeEdge({ ...relationship, aggregate: observedAggregate })));

    const stopped = observed.fire('click');

    expect(stopped.propagation).toBe(true);
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect.mock.calls[0][0].state).toBe('OBSERVED');
    expect(observed.classList.contains(SELECTED_CLASS)).toBe(true);
    expect(selection.selected()).toBe(observed);
  });

  it('opens the inspector for a POSSIBLE edge', () => {
    const possible = fakeEdge('possible');
    const onSelect = vi.fn();
    createEdgeSelection({ onSelect }).bind([possible], () =>
      onSelect(describeEdge({ ...relationship, aggregate: possibleAggregate })),
    );

    possible.fire('click');

    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect.mock.calls[0][0].state).toBe('POSSIBLE');
    expect(possible.classList.contains(SELECTED_CLASS)).toBe(true);
  });

  it('moves the selection to the most recently activated edge', () => {
    const first = fakeEdge('first');
    const second = fakeEdge('second');
    const selection = createEdgeSelection();
    selection.bind([first, second], () => {});

    first.fire('click');
    second.fire('click');

    expect(first.classList.contains(SELECTED_CLASS)).toBe(false);
    expect(second.classList.contains(SELECTED_CLASS)).toBe(true);
  });

  it('drops the selected styling when the inspector closes', () => {
    const observed = fakeEdge('observed');
    const selection = createEdgeSelection();
    selection.bind([observed], () => {});

    observed.fire('click');
    expect(observed.classList.contains(SELECTED_CLASS)).toBe(true);

    selection.clear();

    expect(observed.classList.contains(SELECTED_CLASS)).toBe(false);
    expect(selection.selected()).toBeNull();
  });

  it('leaves node clicks to the existing node behaviour', () => {
    const edge = fakeEdge('edge');
    const node = fakeEdge('node');
    const nodeBehaviour = vi.fn();
    const edgeInspector = vi.fn();
    node.addEventListener('click', nodeBehaviour);
    createEdgeSelection().bind([edge], edgeInspector);

    node.fire('click');

    expect(nodeBehaviour).toHaveBeenCalledTimes(1);
    expect(edgeInspector).not.toHaveBeenCalled();
  });

  it('does not open an inspector for a canvas background click', () => {
    const background = fakeEdge('background');
    const edgeInspector = vi.fn();
    const selection = createEdgeSelection();

    selection.bind([fakeEdge('edge')], edgeInspector);
    background.fire('click');

    expect(edgeInspector).not.toHaveBeenCalled();
    expect(selection.selected()).toBeNull();
  });

  it('honours keyboard activation on a focused edge', () => {
    const edge = fakeEdge('edge');
    const edgeInspector = vi.fn();
    createEdgeSelection().bind([edge], edgeInspector);

    const ignored = edge.fire('keydown', { key: 'a' });
    expect(edgeInspector).not.toHaveBeenCalled();
    expect(ignored.defaultPrevented).toBe(false);

    const activated = edge.fire('keydown', { key: 'Enter' });
    expect(activated.propagation).toBe(true);
    expect(activated.defaultPrevented).toBe(true);
    expect(edgeInspector).toHaveBeenCalledTimes(1);
  });

  it('binds each edge once even when the graph re-renders the same path', () => {
    const edge = fakeEdge('edge');
    const edgeInspector = vi.fn();
    const selection = createEdgeSelection();

    selection.bind([edge], edgeInspector);
    selection.bind([edge], edgeInspector);
    edge.fire('click');

    expect(edgeInspector).toHaveBeenCalledTimes(1);
  });
});

describe('edge inspector wording', () => {
  const app = readFileSync(resolve(frontendRoot, 'app.js'), 'utf8');

  it('names the two levels of state separately', () => {
    expect(app).toContain('Relationship aggregate: ');
    expect(app).toContain('Stored evidence record state');
    expect(app).not.toContain('Evidence aggregate: ');
  });

  it('explains that the aggregate is derived while a pill is one stored record', () => {
    expect(app).toContain('The aggregate is derived from the evidence stored for this relationship.');
    expect(app).toContain('a record can read UNKNOWN while the relationship aggregate reads OBSERVED or POSSIBLE');
  });

  it('does not convert a stored record state into the aggregate state', () => {
    expect(app).toContain("pill(item.state||'UNKNOWN')");
    expect(app).not.toContain("pill(item.state||'OBSERVED')");
  });
});
