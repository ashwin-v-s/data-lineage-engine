/**
 * frontend/src/api/client.js
 * ──────────────────────────
 * The single JSON client used by the React live views (Sources, Freshness,
 * Incidents, asset capabilities).
 *
 * Authentication reuses the app's existing mechanism: `auth.js` installs a
 * global patch on `window.fetch` (see `installApiAuthorization`) that attaches
 * `Authorization: Bearer <token>` to every `/api/v1/*` request. This module
 * therefore issues plain `fetch` calls with the same options convention used by
 * `app.js` and `personalization.js`. No second auth mechanism is introduced.
 *
 * Everything here is environment-agnostic: the fetcher is resolved lazily, so
 * importing this module is safe under Node (unit tests) and in the browser.
 */

/** Base path shared by every Kairos API endpoint. */
export const API_BASE = '/api/v1';

/** Resolve the global fetch lazily so the module stays import-safe in Node. */
function defaultFetcher(url, options) {
  if (typeof fetch !== 'function') {
    return Promise.reject(new Error('Fetch is not available in this environment.'));
  }
  // The global fetch is patched by auth.js to add the bearer token for /api/v1/.
  return fetch(url, options);
}

/** Use the caller's fetcher when supplied, else the patched global fetch. */
export function resolveFetcher(fetcher) {
  return typeof fetcher === 'function' ? fetcher : defaultFetcher;
}

/**
 * Turn a failed response body into a single human-readable sentence.
 *
 * FastAPI reports `{detail: "..."}` for string details and
 * `{detail: {message, diagnostics}}` for structured ones; both shapes are
 * handled so the UI never renders `[object Object]`.
 *
 * @param {unknown} data Parsed response body, when it was JSON.
 * @param {{status: number}} response
 * @returns {string}
 */
export function errorMessage(data, response) {
  const status = response && Number.isFinite(response.status) ? response.status : 0;
  if (data && typeof data === 'object') {
    const detail = data.detail || data.message || data.error;
    if (typeof detail === 'string' && detail) return detail;
    if (detail && typeof detail === 'object' && typeof detail.message === 'string' && detail.message) {
      return detail.message;
    }
  }
  return `Request failed (HTTP ${status}).`;
}

/**
 * Issue a JSON request and return the parsed body.
 *
 * Throws an `Error` whose message is safe to display. Callers that must never
 * throw wrap the call in `try`/`catch` and report `{ ok: false, error }`.
 *
 * @param {string} url
 * @param {{method?: string, body?: unknown, fetcher?: Function}} [options]
 * @returns {Promise<any>}
 */
export async function requestJson(url, { method = 'GET', body, fetcher } = {}) {
  const options = { method, credentials: 'same-origin', headers: { Accept: 'application/json' } };
  if (body !== undefined) {
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(body);
  }
  const response = await resolveFetcher(fetcher)(url, options);
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(errorMessage(data, response));
  return data;
}

/**
 * Coerce a value into a finite number, or `null` when it is not one.
 * @param {unknown} value
 * @returns {number|null}
 */
export function asNumber(value) {
  if (value === null || value === undefined || value === '') return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

/**
 * Coerce a value into a trimmed string, or `null` when it is empty.
 * @param {unknown} value
 * @returns {string|null}
 */
export function asText(value) {
  if (value === null || value === undefined) return null;
  const text = String(value).trim();
  return text === '' ? null : text;
}
