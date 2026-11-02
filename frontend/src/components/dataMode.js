/**
 * Canonical data-provenance vocabulary for the Kairos UI.
 *
 * Every view must be able to state where its data came from. A demonstration
 * fixture must never be presented as live connected data, so the mapping here
 * fails honest: anything that cannot be positively attributed to a live or an
 * imported source is reported as `DEMO FIXTURE`, never as `LIVE`.
 *
 * This module is deliberately DOM-free so it can be unit tested without a
 * browser environment.
 */

export const DATA_MODES = {
  LIVE: 'LIVE',
  IMPORTED: 'IMPORTED',
  DEMO_FIXTURE: 'DEMO FIXTURE',
};

const DESCRIPTIONS = {
  [DATA_MODES.LIVE]: 'Read live from the connected catalog API.',
  [DATA_MODES.IMPORTED]: 'Committed into this workspace by a Kairos import run.',
  [DATA_MODES.DEMO_FIXTURE]: 'Synthetic sample data shown for demonstration only.',
};

const TOKENS = {
  [DATA_MODES.LIVE]: 'live',
  [DATA_MODES.IMPORTED]: 'imported',
  [DATA_MODES.DEMO_FIXTURE]: 'demo-fixture',
};

/** True only for one of the three canonical modes. */
export function isDataMode(value) {
  return value === DATA_MODES.LIVE
    || value === DATA_MODES.IMPORTED
    || value === DATA_MODES.DEMO_FIXTURE;
}

/** Coerce anything into a canonical mode, defaulting to the honest fallback. */
export function normalizeDataMode(value) {
  return isDataMode(value) ? value : DATA_MODES.DEMO_FIXTURE;
}

/**
 * Decide which mode a view is showing.
 *
 * @param {object} [state]
 * @param {'demo'|'postgresql'|string} [state.dataMode] application data mode
 * @param {boolean} [state.demoPreview] the shell was opened as a demo preview
 * @param {boolean} [state.hasImportedRun] the view renders committed import data
 * @returns {string} one of `DATA_MODES`
 */
export function resolveDataMode(state = {}) {
  const { dataMode, demoPreview, hasImportedRun } = state || {};
  if (demoPreview === true) return DATA_MODES.DEMO_FIXTURE;
  if (dataMode === 'demo') return DATA_MODES.DEMO_FIXTURE;
  if (dataMode === 'postgresql') {
    return hasImportedRun === true ? DATA_MODES.IMPORTED : DATA_MODES.LIVE;
  }
  return DATA_MODES.DEMO_FIXTURE;
}

/** Human-readable explanation for a mode, safe for any input. */
export function dataModeDescription(mode) {
  return DESCRIPTIONS[normalizeDataMode(mode)];
}

/** Lower-case, CSS/DOM-safe token for a mode, safe for any input. */
export function dataModeToken(mode) {
  return TOKENS[normalizeDataMode(mode)];
}
