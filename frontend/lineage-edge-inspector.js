/**
 * Lineage canvas edge inspector.
 *
 * The explorer already stores one relationship per canvas edge; this module
 * turns that stored record into the labelled rows the inspector panel shows and
 * owns the click/keyboard selection contract for an edge path.
 *
 * Everything here is presentation only: no field is synthesised, unknown values
 * resolve to ``NOT_RECORDED`` and the evidence state/coverage strings are read
 * from the API response untouched.
 *
 * Loaded as a classic script before ``app.js`` and exported for Node/Vitest
 * through ``module.exports``.
 */
(function (root) {
  'use strict';

  var NOT_RECORDED = 'Not recorded';
  var SELECTED_CLASS = 'lg-edge-selected';

  /** Coverage keys the backend computes, in reading order. */
  var COVERAGE_LABELS = [
    ['coverage_mode', 'Coverage mode'],
    ['scope', 'Coverage scope'],
    ['run_covered', 'Run covered'],
    ['operator_covered', 'Operator covered'],
    ['source_dataset_covered', 'Source dataset covered'],
    ['target_dataset_covered', 'Target dataset covered'],
    ['branches_covered', 'Branches covered'],
    ['parser_status', 'Parser status'],
  ];

  /** Trimmed non-empty string, or null when the value is genuinely absent. */
  function present(value) {
    if (value === undefined || value === null) return null;
    var text = String(value).trim();
    return text === '' ? null : text;
  }

  function coverageValue(value) {
    if (typeof value === 'boolean') return value ? 'Covered' : 'Not covered';
    if (Array.isArray(value)) return value.length ? value.join(', ') : 'None';
    return present(value) || NOT_RECORDED;
  }

  /** Stored coverage object -> labelled rows. Empty for a missing coverage. */
  function coverageRows(coverage) {
    if (!coverage || typeof coverage !== 'object') return [];
    return COVERAGE_LABELS.filter(function (pair) {
      return Object.prototype.hasOwnProperty.call(coverage, pair[0]);
    }).map(function (pair) {
      return { label: pair[1], value: coverageValue(coverage[pair[0]]), known: true };
    });
  }

  function row(label, value) {
    var known = present(value);
    return { label: label, value: known || NOT_RECORDED, known: Boolean(known) };
  }

  /**
   * Identity rows for one relationship.
   *
   * ``granularity`` falls back to the edge type because the graph and the
   * stored edge share that scope (a DATASET edge is dataset granular).
   */
  function relationshipRows(input) {
    var data = input || {};
    return [
      row('Source dataset', data.sourcePath || data.sourceId),
      row('Target dataset', data.targetPath || data.targetId),
      row('Relationship type', data.edgeType),
      row('Granularity', data.granularity || data.edgeType),
      row('Mapping type', data.mappingType),
      row('Edge ID', data.edgeId),
      row('Valid from', data.validFrom),
      row('Recorded from', data.recordedFrom),
    ];
  }

  /** Everything the panel header needs, resolved from stored records only. */
  function describeEdge(input) {
    var data = input || {};
    var aggregate = data.aggregate && typeof data.aggregate === 'object' ? data.aggregate : {};
    var source = present(data.sourcePath) || present(data.sourceId) || 'Unknown source';
    var target = present(data.targetPath) || present(data.targetId) || 'Unknown target';
    return {
      title: 'Lineage relationship evidence',
      heading: source + ' → ' + target,
      state: present(aggregate.state) || NOT_RECORDED,
      coverage: present(aggregate.coverage) || NOT_RECORDED,
      evidenceCount: Number(aggregate.evidence_count) || 0,
      runCount: Number(aggregate.run_count) || 0,
      rows: relationshipRows(data),
      coverageRows: coverageRows(data.coverage),
    };
  }

  /**
   * Make canvas edges selectable.
   *
   * ``onSelect(element)`` runs once per activation; clicks and key presses are
   * stopped from bubbling so the graph's pan/background and node handlers never
   * see an edge activation. ``clear()`` drops the selected styling, which the
   * dashboard calls when the inspector closes.
   */
  /**
   * A selection controller shared by every graph render.
   *
   * ``bind(elements, handler)`` makes each element activate on click or
   * Enter/Space. Activations are stopped from bubbling so the graph's pan,
   * background and node handlers never treat an edge click as their own, and
   * the activated edge carries ``lg-edge-selected`` until ``clear()`` runs
   * (the dashboard calls it when the inspector closes).
   */
  function createEdgeSelection(options) {
    var settings = options || {};
    var fallback = typeof settings.onSelect === 'function' ? settings.onSelect : function () {};
    var selected = null;

    function clear() {
      if (!selected) return;
      selected.classList.remove(SELECTED_CLASS);
      selected = null;
    }

    function activate(element, handler) {
      if (selected && selected !== element) selected.classList.remove(SELECTED_CLASS);
      selected = element;
      if (element.classList) element.classList.add(SELECTED_CLASS);
      (typeof handler === 'function' ? handler : fallback)(element);
    }

    function bind(elements, handler) {
      (elements || []).forEach(function (element) {
        if (!element || typeof element.addEventListener !== 'function') return;
        if (element.__kairosEdgeBound) return;
        element.__kairosEdgeBound = true;
        element.addEventListener('click', function (event) {
          if (event && typeof event.stopPropagation === 'function') event.stopPropagation();
          if (event && typeof event.preventDefault === 'function') event.preventDefault();
          activate(element, handler);
        });
        element.addEventListener('keydown', function (event) {
          if (!event || (event.key !== 'Enter' && event.key !== ' ')) return;
          if (typeof event.preventDefault === 'function') event.preventDefault();
          if (typeof event.stopPropagation === 'function') event.stopPropagation();
          activate(element, handler);
        });
      });
      return api;
    }

    var api = {
      bind: bind,
      clear: clear,
      selected: function () { return selected; },
    };
    return api;
  }

  root.KairosEdgeInspector = {
    NOT_RECORDED: NOT_RECORDED,
    SELECTED_CLASS: SELECTED_CLASS,
    describeEdge: describeEdge,
    coverageRows: coverageRows,
    relationshipRows: relationshipRows,
    createEdgeSelection: createEdgeSelection,
  };
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      NOT_RECORDED: NOT_RECORDED,
      SELECTED_CLASS: SELECTED_CLASS,
      describeEdge: describeEdge,
      coverageRows: coverageRows,
      relationshipRows: relationshipRows,
      createEdgeSelection: createEdgeSelection,
    };
  }
})(typeof window !== 'undefined' ? window : globalThis);
