/**
 * Canonical data-provenance vocabulary for the Kairos UI.
 *
 * Every view must be able to state where its data came from. A demonstration
 * fixture must never be presented as live connected data, so the mapping here
 * fails honest: anything that cannot be positively attributed to a live or an
 * imported source is reported as `NOT CONNECTED`, never as `LIVE`.
 *
 * Two callers feed this module:
 *   - the React shell (`main.jsx`), which knows `demoPreview` and the catalog
 *     request outcome;
 *   - the dashboard script (`app.js`), which knows `dataMode` and
 *     `catalogStatus` (`loading` | `ready` | `error`).
 *
 * Both are accepted by `resolveDataMode`; neither can produce `LIVE` without a
 * positive success signal.
 *
 * This module is deliberately DOM-free so it can be unit tested without a
 * browser environment.
 */

export const DATA_MODES = {
  LIVE: 'LIVE',
  IMPORTED: 'IMPORTED',
  DEMO_FIXTURE: 'DEMO FIXTURE',
  NOT_CONNECTED: 'NOT CONNECTED',
  ERROR: 'CATALOG ERROR',
};

const DESCRIPTIONS = {
  [DATA_MODES.LIVE]: 'Read live from the connected catalog API.',
  [DATA_MODES.IMPORTED]: 'Committed into this workspace by a Kairos import run.',
  [DATA_MODES.DEMO_FIXTURE]: 'Synthetic sample data shown for demonstration only.',
  [DATA_MODES.NOT_CONNECTED]: 'No successful authenticated catalog request is available in this session.',
  [DATA_MODES.ERROR]: 'The authenticated catalog request failed; no fixture data is substituted.',
};

const TOKENS = {
  [DATA_MODES.LIVE]: 'live',
  [DATA_MODES.IMPORTED]: 'imported',
  [DATA_MODES.DEMO_FIXTURE]: 'demo-fixture',
  [DATA_MODES.NOT_CONNECTED]: 'not-connected',
  [DATA_MODES.ERROR]: 'error',
};

/** True only for one of the canonical modes. */
export function isDataMode(value) {
  return value === DATA_MODES.LIVE
    || value === DATA_MODES.IMPORTED
    || value === DATA_MODES.DEMO_FIXTURE
    || value === DATA_MODES.NOT_CONNECTED
    || value === DATA_MODES.ERROR;
}

/** Coerce anything into a canonical mode, defaulting to the safest status. */
export function normalizeDataMode(value) {
  return isDataMode(value) ? value : DATA_MODES.NOT_CONNECTED;
}

/**
 * Decide which mode a view is showing.
 *
 * Precedence: an explicit demo preview, then a failed catalog request, then the
 * catalog status. A dashboard caller that omits `catalogStatus` falls back to
 * the legacy `liveRequestSucceeded` flag so an older caller can never be
 * promoted to `LIVE` by accident.
 *
 * @param {object} [state]
 * @param {'demo'|'postgresql'|string} [state.dataMode] application data mode
 * @param {boolean} [state.demoPreview] the shell was opened as a demo preview
 * @param {'loading'|'ready'|'error'|string} [state.catalogStatus] catalog request state
 * @param {boolean} [state.hasImportedRun] the view renders committed import data
 * @param {boolean} [state.liveRequestSucceeded] an authenticated catalog request succeeded
 * @returns {string} one of `DATA_MODES`
 */
export function resolveDataMode(state = {}) {
  const {
    dataMode,
    demoPreview,
    catalogStatus,
    hasImportedRun,
    liveRequestSucceeded,
  } = state || {};

  if (demoPreview === true) return DATA_MODES.DEMO_FIXTURE;
  if (dataMode === 'demo') return DATA_MODES.DEMO_FIXTURE;

  if (catalogStatus === 'error') return DATA_MODES.ERROR;
  if (catalogStatus !== undefined && catalogStatus !== null) {
    // Only an explicit `ready` status may be promoted beyond NOT CONNECTED.
    if (catalogStatus !== 'ready') return DATA_MODES.NOT_CONNECTED;
    return hasImportedRun === true ? DATA_MODES.IMPORTED : DATA_MODES.LIVE;
  }

  if (dataMode !== 'postgresql' || liveRequestSucceeded !== true) return DATA_MODES.NOT_CONNECTED;
  return hasImportedRun === true ? DATA_MODES.IMPORTED : DATA_MODES.LIVE;
}

/** Human-readable explanation for a mode, safe for any input. */
export function dataModeDescription(mode) {
  return DESCRIPTIONS[normalizeDataMode(mode)];
}

/** Lower-case, CSS/DOM-safe token for a mode, safe for any input. */
export function dataModeToken(mode) {
  return TOKENS[normalizeDataMode(mode)];
}
