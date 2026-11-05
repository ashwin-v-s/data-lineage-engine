/** Canonical provenance labels for records displayed by Kairos. */
export const DATA_MODES = {
  LIVE: 'LIVE',
  IMPORTED: 'IMPORTED',
  NOT_CONNECTED: 'NOT CONNECTED',
  ERROR: 'CATALOG ERROR',
};

const DESCRIPTIONS = {
  [DATA_MODES.LIVE]: 'Read live from the connected catalog API.',
  [DATA_MODES.IMPORTED]: 'Committed into this workspace by a Kairos import run.',
  [DATA_MODES.NOT_CONNECTED]: 'The authenticated catalog request has not succeeded in this page session yet.',
  [DATA_MODES.ERROR]: 'The authenticated catalog request failed. Views show the error instead of substituting sample records.',
};

const TOKENS = {
  [DATA_MODES.LIVE]: 'live',
  [DATA_MODES.IMPORTED]: 'imported',
  [DATA_MODES.NOT_CONNECTED]: 'not-connected',
  [DATA_MODES.ERROR]: 'error',
};

export function isDataMode(value) {
  return Object.values(DATA_MODES).includes(value);
}

export function normalizeDataMode(value) {
  return isDataMode(value) ? value : DATA_MODES.LIVE;
}

export function resolveDataMode(state = {}) {
  const { dataMode, hasImportedRun, catalogStatus } = state || {};
  if (catalogStatus === 'error') return DATA_MODES.ERROR;
  if (catalogStatus !== 'ready') return DATA_MODES.NOT_CONNECTED;
  if (dataMode === 'postgresql' && hasImportedRun === true) return DATA_MODES.IMPORTED;
  return DATA_MODES.LIVE;
}

export function dataModeDescription(mode) {
  return DESCRIPTIONS[normalizeDataMode(mode)];
}

export function dataModeToken(mode) {
  return TOKENS[normalizeDataMode(mode)];
}
