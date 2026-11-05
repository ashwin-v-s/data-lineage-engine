/**
 * frontend/src/views/freshness.js
 * ───────────────────────────────
 * Pure helpers and runtime fetch functions for the Freshness live view.
 *
 * The module is split into two halves, both free of JSX and DOM access:
 *   - Pure builders/normalisers (URL builders, response normalisers, mapping
 *     helpers, form validation, formatting) that can be imported in Node.
 *   - Runtime fetchers that reuse the shared JSON client in `../api/client.js`
 *     and never throw: every failure resolves to `{ ok: false, error }`.
 *
 * Freshness semantics honoured here (see backend/app/services/freshness.py):
 *   - FRESHNESS_STATES = HEALTHY | AT_RISK | LATE | STALE | UNKNOWN.
 *   - UNKNOWN means "no evidence": either no SLA is configured or no source
 *     activity has ever been observed. It is never presented as LATE/STALE, and
 *     `age_minutes` is null for UNKNOWN.
 *   - Incident severity (opened by the backend): STALE -> HIGH, LATE -> MEDIUM,
 *     otherwise LOW.
 */

import { API_BASE, asNumber, asText, requestJson } from '../api/client.js';

/** The freshness states, in presentation order. */
export const FRESHNESS_STATES = ['HEALTHY', 'AT_RISK', 'LATE', 'STALE', 'UNKNOWN'];

/** The source signals an SLA may be built on. */
export const SLA_SIGNALS = ['openlineage_run', 'dbt_run_results', 'updated_at', 'manual'];

/* ────────────────────────── pure URL builders ────────────────────────── */

/** The latest freshness verdict per dataset. */
export function buildFreshnessUrl() {
  return `${API_BASE}/governance/freshness`;
}

/** The workspace's freshness SLAs. */
export function buildSlasUrl() {
  return `${API_BASE}/governance/slas`;
}

/**
 * Build the URL that runs the freshness engine for one dataset.
 * @param {string} assetId Dataset UUID or dataset name.
 * @returns {string}
 */
export function buildEvaluateUrl(assetId) {
  return `${API_BASE}/governance/datasets/${encodeURIComponent(String(assetId ?? ''))}/evaluate`;
}

/* ──────────────────────────── small helpers ──────────────────────────── */

/** Coerce any value into a plain (non-array) record, else an empty object. */
function asRecord(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
}

/** A counts object with every state at zero. */
function zeroCounts() {
  const counts = {};
  for (const state of FRESHNESS_STATES) counts[state] = 0;
  return counts;
}

/** True when `value` is a positive integer (numbers and numeric strings). */
function isPositiveInteger(value) {
  if (value === '' || value === null || value === undefined) return false;
  const n = Number(value);
  return Number.isInteger(n) && n > 0;
}

/* ────────────────────────── pure normalisers ────────────────────────── */

/**
 * Normalise one raw evaluation into a stable shape. Any unrecognised `state`
 * becomes `'UNKNOWN'`; missing fields degrade to `null` rather than throwing.
 * @param {unknown} raw
 */
export function normalizeEvaluation(raw) {
  const source = asRecord(raw);
  const state = FRESHNESS_STATES.includes(source.state) ? source.state : 'UNKNOWN';
  return {
    id: asText(source.id),
    datasetId: asText(source.dataset_id),
    datasetName: asText(source.dataset_name),
    state,
    ageMinutes: asNumber(source.age_minutes),
    thresholdMinutes: asNumber(source.threshold_minutes),
    reason: asText(source.reason),
    lastSourceActivityAt: asText(source.last_source_activity_at),
    evidenceId: asText(source.evidence_id),
    evaluatedAt: asText(source.evaluated_at),
  };
}

/**
 * Normalise the freshness payload into `{ evaluations, counts, total, unknownCount }`.
 *
 * `counts` always contains all five states (a missing state is 0). When the
 * payload omits `counts` entirely it is derived from the evaluations; when it
 * omits `total` the derived (evaluation) count is used.
 * @param {unknown} payload
 */
export function normalizeFreshnessPayload(payload) {
  const source = asRecord(payload);
  const rawEvaluations = Array.isArray(source.evaluations) ? source.evaluations : [];
  const evaluations = rawEvaluations
    .filter((entry) => entry && typeof entry === 'object' && !Array.isArray(entry))
    .map(normalizeEvaluation);

  const derived = zeroCounts();
  for (const item of evaluations) derived[item.state] += 1;

  let counts;
  if (source.counts && typeof source.counts === 'object' && !Array.isArray(source.counts)) {
    counts = zeroCounts();
    for (const state of FRESHNESS_STATES) {
      const value = asNumber(source.counts[state]);
      if (value !== null) counts[state] = value;
    }
  } else {
    counts = derived;
  }

  const total = asNumber(source.total);
  return {
    evaluations,
    counts,
    total: total === null ? evaluations.length : total,
    unknownCount: counts.UNKNOWN,
  };
}

/**
 * Normalise one raw SLA record.
 * @param {unknown} raw
 */
export function normalizeSla(raw) {
  const source = asRecord(raw);
  return {
    id: asText(source.id),
    datasetId: asText(source.dataset_id),
    datasetName: asText(source.dataset_name),
    warnAfterMinutes: asNumber(source.warn_after_minutes),
    errorAfterMinutes: asNumber(source.error_after_minutes),
    staleAfterMinutes: asNumber(source.stale_after_minutes),
    signal: asText(source.signal),
    createdAt: asText(source.created_at),
  };
}

/**
 * Normalise an SLA list payload into `{ slas, count }`.
 * @param {unknown} payload
 */
export function normalizeSlaList(payload) {
  const source = asRecord(payload);
  const rawSlas = Array.isArray(source.slas) ? source.slas : [];
  const slas = rawSlas
    .filter((entry) => entry && typeof entry === 'object' && !Array.isArray(entry))
    .map(normalizeSla);
  const count = asNumber(source.count);
  return { slas, count: count === null ? slas.length : count };
}

/**
 * Normalise the evaluate endpoint's response into a flat outcome. Reads the
 * nested `verdict` when present, and defaults `incidentAction` to `'none'`.
 * @param {unknown} payload
 */
export function normalizeEvaluationOutcome(payload) {
  const source = asRecord(payload);
  const verdict = source.verdict && typeof source.verdict === 'object' && !Array.isArray(source.verdict)
    ? source.verdict
    : source;
  return {
    state: FRESHNESS_STATES.includes(verdict.state) ? verdict.state : 'UNKNOWN',
    ageMinutes: asNumber(verdict.age_minutes),
    thresholdMinutes: asNumber(verdict.threshold_minutes),
    reason: asText(verdict.reason),
    incidentAction: asText(source.incident_action) || 'none',
    incidentId: asText(source.incident_id),
  };
}

/* ───────────────────────── presentation mappings ───────────────────────── */

const CHIP_TOKENS = {
  HEALTHY: 'ok',
  AT_RISK: 'warn',
  LATE: 'bad',
  STALE: 'bad',
  UNKNOWN: 'muted',
};

/** The `.kv-chip--<token>` token for a freshness state. */
export function freshnessChipToken(state) {
  return CHIP_TOKENS[state] || 'muted';
}

const EXPLANATIONS = {
  HEALTHY: 'Source activity is within the warning threshold; the dataset is fresh.',
  AT_RISK: 'Source activity has passed the warning threshold but not the error threshold.',
  LATE: 'Source activity has passed the error threshold; the dataset is late.',
  STALE: 'Source activity has passed the stale threshold; the dataset is stale.',
  UNKNOWN: 'Kairos reports UNKNOWN rather than LATE because no source activity has been observed '
    + '(or no SLA is configured); it never assumes staleness without evidence.',
};

/** One honest sentence describing what a state means. */
export function freshnessExplanation(state) {
  return EXPLANATIONS[state]
    || 'Kairos reports UNKNOWN rather than LATE because no source activity has been observed.';
}

const INCIDENT_SENTENCES = {
  created: 'An incident was opened for this breach.',
  existing: 'An open incident already covers this breach.',
  none: 'No incident was required for this verdict.',
  resolved: 'The open incident for this dataset was resolved.',
};

/** A human sentence for an evaluate call's `incident_action`. */
export function incidentActionSentence(action) {
  return INCIDENT_SENTENCES[action] || 'No incident action was reported.';
}

/* ──────────────────────────── form helpers ──────────────────────────── */

/** A blank SLA form with sensible defaults. */
export function emptySlaForm() {
  return {
    asset_id: '',
    warn_after_minutes: 60,
    error_after_minutes: 180,
    stale_after_minutes: '',
    signal: 'updated_at',
  };
}

/**
 * Validate an SLA form. Rules: a required `asset_id`; a positive-integer
 * `warn_after_minutes`; an integer `error_after_minutes` strictly greater than
 * warn; an empty/null or positive-integer `stale_after_minutes`; and a `signal`
 * drawn from `SLA_SIGNALS`.
 * @param {unknown} input
 * @returns {{valid: boolean, errors: Array<{field: string, message: string}>}}
 */
export function validateSlaInput(input) {
  const source = asRecord(input);
  const errors = [];

  if (!asText(source.asset_id)) {
    errors.push({ field: 'asset_id', message: 'An asset id or dataset name is required.' });
  }

  const warn = source.warn_after_minutes;
  const error = source.error_after_minutes;
  const warnValid = isPositiveInteger(warn);
  if (!warnValid) {
    errors.push({ field: 'warn_after_minutes', message: 'Warn after must be a positive whole number of minutes.' });
  }
  if (!isPositiveInteger(error)) {
    errors.push({ field: 'error_after_minutes', message: 'Error after must be a positive whole number of minutes.' });
  } else if (warnValid && !(Number(error) > Number(warn))) {
    errors.push({ field: 'error_after_minutes', message: 'Error after must be greater than warn after.' });
  }

  const stale = source.stale_after_minutes;
  if (!(stale === '' || stale === null || stale === undefined) && !isPositiveInteger(stale)) {
    errors.push({ field: 'stale_after_minutes', message: 'Stale after must be empty or a positive whole number of minutes.' });
  }

  if (!SLA_SIGNALS.includes(source.signal)) {
    errors.push({ field: 'signal', message: `Signal must be one of: ${SLA_SIGNALS.join(', ')}.` });
  }

  return { valid: errors.length === 0, errors };
}

/* ──────────────────────────── formatting ──────────────────────────── */

/**
 * Human duration for an age in minutes: `'45m'`, `'3h 20m'`, `'2d 4h'`.
 * Non-finite or negative input renders `'—'`.
 * @param {number|null} minutes
 */
export function formatAge(minutes) {
  const value = asNumber(minutes);
  if (value === null || value < 0) return '—';
  const total = Math.floor(value);
  const days = Math.floor(total / 1440);
  const hours = Math.floor((total % 1440) / 60);
  const mins = total % 60;
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${mins}m`;
  return `${mins}m`;
}

/**
 * Render a timestamp losslessly: the raw string is returned unchanged (no
 * timezone is invented). `null`/empty renders `'—'`; a `Date` is serialised.
 * @param {unknown} value
 */
export function formatTimestamp(value) {
  if (value === null || value === undefined || value === '') return '—';
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? '—' : value.toISOString();
  return String(value);
}

/* ─────────────────────────── runtime fetchers ─────────────────────────── */

/**
 * Fetch the latest freshness verdict per dataset. Never throws.
 * @param {{fetcher?: Function}} [options]
 * @returns {Promise<{ok: true, evaluations: Array, counts: object, total: number}
 *   | {ok: false, error: string, evaluations: Array, counts: object, total: number}>}
 */
export async function fetchFreshness({ fetcher } = {}) {
  try {
    const data = await requestJson(buildFreshnessUrl(), { fetcher });
    const normalised = normalizeFreshnessPayload(data);
    return {
      ok: true,
      evaluations: normalised.evaluations,
      counts: normalised.counts,
      total: normalised.total,
    };
  } catch (error) {
    return {
      ok: false,
      error: error.message || 'The freshness list could not be loaded.',
      evaluations: [],
      counts: zeroCounts(),
      total: 0,
    };
  }
}

/**
 * Fetch the workspace's freshness SLAs. Never throws.
 * @param {{fetcher?: Function}} [options]
 * @returns {Promise<{ok: true, slas: Array, count: number} | {ok: false, error: string, slas: Array, count: number}>}
 */
export async function fetchSlas({ fetcher } = {}) {
  try {
    const data = await requestJson(buildSlasUrl(), { fetcher });
    const normalised = normalizeSlaList(data);
    return { ok: true, slas: normalised.slas, count: normalised.count };
  } catch (error) {
    return { ok: false, error: error.message || 'The freshness SLAs could not be loaded.', slas: [], count: 0 };
  }
}

/**
 * Create or replace the freshness SLA for one dataset. Never throws.
 * @param {object} input SLA body sent to the API.
 * @param {{fetcher?: Function}} [options]
 * @returns {Promise<{ok: true, sla: object} | {ok: false, error: string}>}
 */
export async function upsertSla(input, { fetcher } = {}) {
  try {
    const data = await requestJson(buildSlasUrl(), { method: 'POST', body: input, fetcher });
    return { ok: true, sla: normalizeSla(data) };
  } catch (error) {
    return { ok: false, error: error.message || 'The freshness SLA could not be saved.' };
  }
}

/**
 * Run the freshness engine for one dataset. Never throws.
 * @param {string} assetId Dataset UUID or dataset name.
 * @param {{fetcher?: Function}} [options]
 * @returns {Promise<{ok: true, outcome: object} | {ok: false, error: string}>}
 */
export async function evaluateDataset(assetId, { fetcher } = {}) {
  try {
    const data = await requestJson(buildEvaluateUrl(assetId), { method: 'POST', fetcher });
    return { ok: true, outcome: normalizeEvaluationOutcome(data) };
  } catch (error) {
    return { ok: false, error: error.message || 'The dataset could not be evaluated.' };
  }
}
