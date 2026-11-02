/**
 * frontend/src/views/incidents.js
 * ─────────────────────────────────
 * Pure helpers and runtime fetch functions for the Kairos Incident console.
 *
 * This module is deliberately DOM-free and JSX-free: importing it is safe under
 * Node (unit tests) and in the browser. It mirrors the live backend contract in
 * `backend/app/api/routes/governance.py` and the transition table in
 * `backend/app/services/freshness.py` exactly — no status, severity or action
 * value is invented here.
 *
 * Backend contract (base `/api/v1`):
 *   GET  /governance/incidents?status=<STATUS>       -> { incidents: Incident[], count }
 *   GET  /governance/incidents/{incident_id}          -> Incident + { events: IncidentEvent[] }
 *   POST /governance/incidents/{incident_id}/{action} -> Incident + events (409 on illegal)
 *
 * Vocabulary (source of truth):
 *   status   ∈ DETECTED | ACKNOWLEDGED | INVESTIGATING | RESOLVED
 *   severity ∈ LOW | MEDIUM | HIGH
 *   action   ∈ acknowledge | investigate | resolve
 */

import { API_BASE, asText, requestJson } from '../api/client.js';

/* ─────────────────────────────── constants ─────────────────────────────── */

/** Incident lifecycle statuses, in progression order. */
export const INCIDENT_STATUSES = ['DETECTED', 'ACKNOWLEDGED', 'INVESTIGATING', 'RESOLVED'];

/** Incident severities. */
export const INCIDENT_SEVERITIES = ['LOW', 'MEDIUM', 'HIGH'];

/** Actions a user may apply to an incident, in the order the UI offers them. */
export const INCIDENT_ACTIONS = ['acknowledge', 'investigate', 'resolve'];

/**
 * Allowed transitions — mirrors `freshness._TRANSITIONS` exactly. A status
 * absent from this table (or a missing action) means the transition is illegal.
 */
const TRANSITIONS = {
  DETECTED: { acknowledge: 'ACKNOWLEDGED', investigate: 'INVESTIGATING', resolve: 'RESOLVED' },
  ACKNOWLEDGED: { investigate: 'INVESTIGATING', resolve: 'RESOLVED' },
  INVESTIGATING: { resolve: 'RESOLVED' },
  RESOLVED: {},
};

const ACTION_PAST_TENSE = {
  acknowledge: 'Acknowledged',
  investigate: 'Investigated',
  resolve: 'Resolved',
};

/* ────────────────────────────── URL builders ───────────────────────────── */

/**
 * Build the incidents list URL. A nullish/empty status, or the `ALL` sentinel,
 * omits the query parameter entirely (the API then returns every status).
 * @param {string|null|undefined} [status]
 * @returns {string}
 */
export function buildIncidentsUrl(status) {
  const normalized = asText(status);
  if (!normalized || normalized === 'ALL') {
    return `${API_BASE}/governance/incidents`;
  }
  return `${API_BASE}/governance/incidents?status=${encodeURIComponent(normalized)}`;
}

/**
 * Build the single-incident URL.
 * @param {string} id
 * @returns {string}
 */
export function buildIncidentUrl(id) {
  return `${API_BASE}/governance/incidents/${encodeURIComponent(String(id ?? ''))}`;
}

/**
 * Build the URL for an incident action (`acknowledge` / `investigate` / `resolve`).
 * @param {string} id
 * @param {string} action
 * @returns {string}
 */
export function buildIncidentActionUrl(id, action) {
  return `${API_BASE}/governance/incidents/${encodeURIComponent(String(id ?? ''))}/${encodeURIComponent(String(action ?? ''))}`;
}

/* ────────────────────────────── normalisers ────────────────────────────── */

/** Coerce a raw payload into a plain object, or `{}` for anything else. */
function asObject(raw) {
  return raw && typeof raw === 'object' && !Array.isArray(raw) ? raw : {};
}

/**
 * Normalise a raw incident into a stable camelCase shape. Never throws and
 * tolerates null/garbage. An unrecognised status becomes `DETECTED` and an
 * unrecognised severity becomes `LOW`.
 * @param {unknown} raw
 * @returns {{id: string|null, datasetId: string|null, datasetName: string|null,
 *   title: string|null, severity: string, status: string, dedupeKey: string|null,
 *   openedAt: string|null, acknowledgedAt: string|null, resolvedAt: string|null,
 *   ownerUserId: string|null, detail: unknown, events: Array}}
 */
export function normalizeIncident(raw) {
  const source = asObject(raw);
  const status = INCIDENT_STATUSES.includes(source.status) ? source.status : 'DETECTED';
  const severity = INCIDENT_SEVERITIES.includes(source.severity) ? source.severity : 'LOW';
  return {
    id: asText(source.id),
    datasetId: asText(source.dataset_id),
    datasetName: asText(source.dataset_name),
    title: asText(source.title),
    severity,
    status,
    dedupeKey: asText(source.dedupe_key),
    openedAt: asText(source.opened_at),
    acknowledgedAt: asText(source.acknowledged_at),
    resolvedAt: asText(source.resolved_at),
    ownerUserId: asText(source.owner_user_id),
    detail: source.detail ?? null,
    events: [],
  };
}

/**
 * Normalise a raw incident list payload into `{ incidents, count }`. Accepts a
 * bare array too. Entries with no resolvable `id` are dropped.
 * @param {unknown} payload
 * @returns {{incidents: Array, count: number}}
 */
export function normalizeIncidentList(payload) {
  let rawItems = [];
  let rawCount = null;
  if (Array.isArray(payload)) {
    rawItems = payload;
  } else {
    const source = asObject(payload);
    rawItems = Array.isArray(source.incidents) ? source.incidents : [];
    rawCount = source.count;
  }
  const incidents = rawItems
    .filter((entry) => entry && typeof entry === 'object' && !Array.isArray(entry))
    .map(normalizeIncident)
    .filter((entry) => entry.id);
  const count = Number.isFinite(rawCount) ? rawCount : incidents.length;
  return { incidents, count };
}

/**
 * Normalise a raw incident event.
 * @param {unknown} raw
 * @returns {{id: string|null, eventType: string|null, actorUserId: string|null,
 *   detail: unknown, createdAt: string|null}}
 */
export function normalizeIncidentEvent(raw) {
  const source = asObject(raw);
  return {
    id: asText(source.id),
    eventType: asText(source.event_type),
    actorUserId: asText(source.actor_user_id),
    detail: source.detail ?? null,
    createdAt: asText(source.created_at),
  };
}

/**
 * Normalise an incident detail payload (an incident plus its event timeline).
 * A missing/!array `events` degrades to `[]`; events keep arrival order.
 * @param {unknown} payload
 * @returns {ReturnType<typeof normalizeIncident>}
 */
export function normalizeIncidentDetail(payload) {
  const incident = normalizeIncident(payload);
  const source = asObject(payload);
  const events = Array.isArray(source.events)
    ? source.events
      .filter((entry) => entry && typeof entry === 'object' && !Array.isArray(entry))
      .map(normalizeIncidentEvent)
    : [];
  return { ...incident, events };
}

/**
 * Convenience wrapper around an action response: `ok` is true only when a
 * normalised incident with an `id` was returned.
 * @param {unknown} payload
 * @returns {{ok: boolean, incident: ReturnType<typeof normalizeIncidentDetail>,
 *   error: string|null}}
 */
export function normalizeActionOutcome(payload) {
  const incident = normalizeIncidentDetail(payload);
  if (incident.id) {
    return { ok: true, incident, error: null };
  }
  const source = asObject(payload);
  const error = asText(source.detail) || asText(source.message) || 'The incident action returned no incident.';
  return { ok: false, incident, error };
}

/* ─────────────────────────── derived helpers ─────────────────────────── */

/**
 * The subset of `INCIDENT_ACTIONS` legal from `status`, in canonical order.
 * An unknown status yields an empty list.
 * @param {string} status
 * @returns {string[]}
 */
export function allowedIncidentActions(status) {
  const table = TRANSITIONS[status];
  if (!table) return [];
  return INCIDENT_ACTIONS.filter((action) => Object.prototype.hasOwnProperty.call(table, action));
}

/**
 * Chip token for a status, mapping onto `kv-chip--<token>`.
 * @param {string} status
 * @returns {'bad'|'warn'|'info'|'ok'|'muted'}
 */
export function incidentStatusChipToken(status) {
  switch (status) {
    case 'DETECTED': return 'bad';
    case 'ACKNOWLEDGED': return 'warn';
    case 'INVESTIGATING': return 'info';
    case 'RESOLVED': return 'ok';
    default: return 'muted';
  }
}

/**
 * Chip token for a severity, mapping onto `kv-chip--<token>`.
 * @param {string} severity
 * @returns {'bad'|'warn'|'muted'}
 */
export function incidentSeverityChipToken(severity) {
  switch (severity) {
    case 'HIGH': return 'bad';
    case 'MEDIUM': return 'warn';
    case 'LOW': return 'muted';
    default: return 'muted';
  }
}

/**
 * True while an incident is not yet resolved.
 * @param {{status?: string}|null|undefined} incident
 * @returns {boolean}
 */
export function isOpenIncident(incident) {
  const status = incident && typeof incident === 'object' ? incident.status : undefined;
  return status !== 'RESOLVED';
}

/**
 * One honest sentence describing a status.
 * @param {string} status
 * @returns {string}
 */
export function statusExplanation(status) {
  switch (status) {
    case 'DETECTED':
      return 'The freshness engine detected an SLA breach and opened this incident; nobody has acted on it yet.';
    case 'ACKNOWLEDGED':
      return 'Someone has acknowledged the breach; it has an owner but investigation has not started.';
    case 'INVESTIGATING':
      return 'The breach is being investigated.';
    case 'RESOLVED':
      return 'The incident is resolved and no further action is possible.';
    default:
      return `'${status ?? 'UNKNOWN'}' is not a recognised incident status.`;
  }
}

/**
 * One sentence describing a severity, tying HIGH to a STALE freshness verdict
 * and MEDIUM to LATE.
 * @param {string} severity
 * @returns {string}
 */
export function severityExplanation(severity) {
  switch (severity) {
    case 'HIGH':
      return 'High severity: the dataset breached its stale threshold (a STALE freshness verdict).';
    case 'MEDIUM':
      return 'Medium severity: the dataset breached its late threshold (a LATE freshness verdict).';
    case 'LOW':
      return 'Low severity: the breach is neither STALE nor LATE, so it is tracked at the lowest severity.';
    default:
      return `'${severity ?? 'UNKNOWN'}' is not a recognised incident severity.`;
  }
}

/**
 * Describe the effect of applying `action` to an incident in `previousStatus`.
 * For a legal pair this reads e.g. "Acknowledged — the incident is now
 * ACKNOWLEDGED."; for an illegal pair it says the action is unavailable. Never
 * throws.
 * @param {string} previousStatus
 * @param {string} action
 * @returns {string}
 */
export function summarizeTransition(previousStatus, action) {
  const table = TRANSITIONS[previousStatus];
  if (!table || !Object.prototype.hasOwnProperty.call(table, action)) {
    return `The '${action}' action is not available while the incident is in status '${previousStatus ?? 'UNKNOWN'}'.`;
  }
  const nextStatus = table[action];
  const label = ACTION_PAST_TENSE[action] || action;
  return `${label} — the incident is now ${nextStatus}.`;
}

/**
 * A lossless display string for a timestamp: the raw value is returned
 * unchanged (no reformatting, so no timezone is invented). Never throws.
 * @param {unknown} value
 * @returns {string}
 */
export function formatTimestamp(value) {
  if (value === null || value === undefined) return '';
  try {
    return String(value);
  } catch (_error) {
    return '';
  }
}

/* ───────────────────────────── runtime (fetch) ───────────────────────────── */

/**
 * Fetch the incident list. Never throws.
 * @param {{status?: string|null, fetcher?: Function}} [options]
 * @returns {Promise<{ok: true, incidents: Array, count: number}
 *   | {ok: false, error: string, incidents: [], count: 0}>}
 */
export async function fetchIncidents({ status, fetcher } = {}) {
  try {
    const data = await requestJson(buildIncidentsUrl(status), { fetcher });
    const { incidents, count } = normalizeIncidentList(data);
    return { ok: true, incidents, count };
  } catch (error) {
    return {
      ok: false,
      error: (error && error.message) || 'Could not load incidents from the live API.',
      incidents: [],
      count: 0,
    };
  }
}

/**
 * Fetch one incident with its event timeline. Never throws.
 * @param {string} id
 * @param {{fetcher?: Function}} [options]
 * @returns {Promise<{ok: true, incident: object} | {ok: false, error: string}>}
 */
export async function fetchIncident(id, { fetcher } = {}) {
  try {
    const data = await requestJson(buildIncidentUrl(id), { fetcher });
    return { ok: true, incident: normalizeIncidentDetail(data) };
  } catch (error) {
    return { ok: false, error: (error && error.message) || 'Could not load the incident.' };
  }
}

/**
 * Apply an incident action. Never throws; a 409 surfaces the API's `detail`
 * string as a readable sentence.
 * @param {string} id
 * @param {string} action
 * @param {{fetcher?: Function}} [options]
 * @returns {Promise<{ok: true, incident: object} | {ok: false, error: string}>}
 */
export async function applyIncidentAction(id, action, { fetcher } = {}) {
  try {
    const data = await requestJson(buildIncidentActionUrl(id, action), { method: 'POST', fetcher });
    return { ok: true, incident: normalizeIncidentDetail(data) };
  } catch (error) {
    return { ok: false, error: (error && error.message) || 'Could not apply the incident action.' };
  }
}
