/**
 * frontend/personalization.js
 * ───────────────────────────
 * Additive "Quick access" feature for the Kairos frontend: a panel that lists
 * the signed-in user's recently viewed and starred assets, plus a control to
 * toggle a star on a given asset id.
 *
 * Authentication reuses the app's existing mechanism: `auth.js` installs a
 * global patch on `window.fetch` (see `installApiAuthorization`) that attaches
 * `Authorization: Bearer <token>` to every `/api/v1/*` request. This module
 * therefore issues plain `fetch` calls with the same options convention used
 * across `app.js` (`credentials: 'same-origin'`, `Accept: application/json`).
 * No second auth mechanism is introduced.
 *
 * The module is intentionally split in two:
 *   - Pure helpers (URL builders and response normalisers) with no DOM access,
 *     so they can be imported and unit-tested in Node.
 *   - DOM/runtime helpers that only touch `document`/`window` when explicitly
 *     called, so merely importing this module never touches the DOM.
 *
 * Public API (see named exports below):
 *   URL builders      : API_BASE, buildRecentlyViewedUrl, buildRecentlyViewedRecordUrl,
 *                       buildClearRecentlyViewedUrl, buildStarredAssetsUrl, buildStarUrl
 *   Normalisers       : normalizeAsset, normalizeAssetList, normalizeMutationResult
 *   Runtime           : fetchRecentlyViewed, fetchStarredAssets, starAsset, unstarAsset,
 *                       toggleStar, mountPanel
 *
 * Backend contract (backend/app/api/routes/personalization.py):
 *   GET    /api/v1/me/recently-viewed?limit=N -> { items: PersonalizedAsset[], total: int }
 *   POST   /api/v1/me/recently-viewed/{asset_id} -> MutationResult
 *   DELETE /api/v1/me/recently-viewed         -> MutationResult
 *   GET    /api/v1/me/starred-assets          -> { items: PersonalizedAsset[], total: int }
 *   POST   /api/v1/assets/{asset_id}/star     -> MutationResult
 *   DELETE /api/v1/assets/{asset_id}/star     -> MutationResult
 * where PersonalizedAsset = { asset_id, name, asset_type?, schema_name?,
 *   database_name?, source_system?, qualified_name?, recorded_at? }
 * and MutationResult = { ok, asset_id?, starred?, deleted? }.
 */

/** Base path shared by every personalization endpoint. */
export const API_BASE = '/api/v1';

/* ────────────────────────── pure URL builders ────────────────────────── */

/**
 * Build the URL for the caller's recently viewed list.
 * @param {number} [limit] Optional page size (1-50); omitted when not a valid number.
 * @returns {string}
 */
export function buildRecentlyViewedUrl(limit) {
  const n = Number(limit);
  if (Number.isFinite(n) && n > 0) {
    return `${API_BASE}/me/recently-viewed?limit=${Math.floor(n)}`;
  }
  return `${API_BASE}/me/recently-viewed`;
}

/**
 * Build the URL used to record an asset view.
 * @param {string} assetId Asset id or dataset name.
 * @returns {string}
 */
export function buildRecentlyViewedRecordUrl(assetId) {
  return `${API_BASE}/me/recently-viewed/${encodeURIComponent(String(assetId ?? ''))}`;
}

/**
 * Build the URL used to clear the caller's view history.
 * @returns {string}
 */
export function buildClearRecentlyViewedUrl() {
  return `${API_BASE}/me/recently-viewed`;
}

/**
 * Build the URL for the caller's starred assets list.
 * @returns {string}
 */
export function buildStarredAssetsUrl() {
  return `${API_BASE}/me/starred-assets`;
}

/**
 * Build the URL used to star or unstar an asset (method distinguishes the two).
 * @param {string} assetId Asset id or dataset name.
 * @returns {string}
 */
export function buildStarUrl(assetId) {
  return `${API_BASE}/assets/${encodeURIComponent(String(assetId ?? ''))}/star`;
}

/* ──────────────────────── pure response normalisers ──────────────────────── */

/**
 * Normalise a single raw asset record into a stable, DOM-friendly shape.
 * Missing fields degrade to empty strings / null rather than throwing.
 * @param {unknown} raw
 * @returns {{assetId: string, name: string, assetType: string|null,
 *   schemaName: string|null, databaseName: string|null, sourceSystem: string|null,
 *   qualifiedName: string|null, recordedAt: string|null}}
 */
export function normalizeAsset(raw) {
  const source = raw && typeof raw === 'object' ? raw : {};
  const qualifiedName = source.qualified_name ?? null;
  const assetId = source.asset_id ?? qualifiedName ?? '';
  const name = source.name ?? qualifiedName ?? '';
  return {
    assetId: assetId == null ? '' : String(assetId),
    name: name == null ? '' : String(name),
    assetType: source.asset_type ?? null,
    schemaName: source.schema_name ?? null,
    databaseName: source.database_name ?? null,
    sourceSystem: source.source_system ?? null,
    qualifiedName,
    recordedAt: source.recorded_at ?? null,
  };
}

/**
 * Normalise a list response into `{ items, total }`. Non-object payloads,
 * missing/!array `items`, and items without an id are handled defensively.
 * @param {unknown} payload
 * @returns {{items: Array<ReturnType<typeof normalizeAsset>>, total: number}}
 */
export function normalizeAssetList(payload) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return { items: [], total: 0 };
  }
  const rawItems = Array.isArray(payload.items) ? payload.items : [];
  const items = rawItems
    .filter((entry) => entry && typeof entry === 'object')
    .map(normalizeAsset)
    .filter((entry) => entry.assetId);
  const total = Number.isFinite(payload.total) ? payload.total : items.length;
  return { items, total };
}

/**
 * Normalise a mutation response into a stable shape.
 * @param {unknown} payload
 * @returns {{ok: boolean, assetId: string|null, starred: boolean|null,
 *   deleted: number|null, error: string|null}}
 */
export function normalizeMutationResult(payload) {
  const source = payload && typeof payload === 'object' && !Array.isArray(payload) ? payload : {};
  return {
    ok: source.ok === true,
    assetId: source.asset_id == null ? null : String(source.asset_id),
    starred: typeof source.starred === 'boolean' ? source.starred : null,
    deleted: Number.isFinite(source.deleted) ? source.deleted : null,
    error: typeof source.error === 'string' ? source.error : null,
  };
}

/* ─────────────────────────── runtime (DOM / fetch) ─────────────────────────── */

/** Resolve the global fetch lazily so the module stays import-safe in Node. */
function defaultFetcher(url, options) {
  if (typeof fetch !== 'function') {
    return Promise.reject(new Error('Fetch is not available in this environment.'));
  }
  // The global fetch is patched by auth.js to add the bearer token for /api/v1/.
  return fetch(url, options);
}

function resolveFetcher(fetcher) {
  return typeof fetcher === 'function' ? fetcher : defaultFetcher;
}

function errorMessage(data, response) {
  if (data && typeof data === 'object') {
    const detail = data.detail || data.message || data.error;
    if (typeof detail === 'string' && detail) return detail;
    if (detail && typeof detail === 'object' && typeof detail.message === 'string') return detail.message;
  }
  return `Request failed (HTTP ${response.status}).`;
}

async function requestJson(url, { method = 'GET', body, fetcher } = {}) {
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
 * Fetch the caller's recently viewed assets.
 * @param {{limit?: number, fetcher?: Function}} [options]
 * @returns {Promise<{items: Array, total: number}>}
 */
export async function fetchRecentlyViewed(options = {}) {
  const data = await requestJson(buildRecentlyViewedUrl(options.limit), { fetcher: options.fetcher });
  return normalizeAssetList(data);
}

/**
 * Fetch the caller's starred assets.
 * @param {{fetcher?: Function}} [options]
 * @returns {Promise<{items: Array, total: number}>}
 */
export async function fetchStarredAssets(options = {}) {
  const data = await requestJson(buildStarredAssetsUrl(), { fetcher: options.fetcher });
  return normalizeAssetList(data);
}

/**
 * Star an asset. Never throws: failures resolve to `{ ok: false, error }`.
 * @param {string} assetId
 * @param {{fetcher?: Function}} [options]
 * @returns {Promise<ReturnType<typeof normalizeMutationResult>>}
 */
export async function starAsset(assetId, options = {}) {
  try {
    const data = await requestJson(buildStarUrl(assetId), { method: 'POST', fetcher: options.fetcher });
    return normalizeMutationResult({ starred: true, ...data });
  } catch (error) {
    return { ok: false, assetId: String(assetId ?? ''), starred: null, deleted: null, error: error.message || 'Could not star the asset.' };
  }
}

/**
 * Remove the caller's star from an asset. Never throws.
 * @param {string} assetId
 * @param {{fetcher?: Function}} [options]
 * @returns {Promise<ReturnType<typeof normalizeMutationResult>>}
 */
export async function unstarAsset(assetId, options = {}) {
  try {
    const data = await requestJson(buildStarUrl(assetId), { method: 'DELETE', fetcher: options.fetcher });
    return normalizeMutationResult({ starred: false, ...data });
  } catch (error) {
    return { ok: false, assetId: String(assetId ?? ''), starred: null, deleted: null, error: error.message || 'Could not remove the star.' };
  }
}

/**
 * Toggle a star for an asset. `nextStarred` selects the target state; when
 * omitted the current state is flipped. Never throws — a failure is returned
 * with `ok: false` so callers can surface it as a non-blocking message.
 * @param {string} assetId
 * @param {boolean|{starred?: boolean, current?: boolean, fetcher?: Function}} [stateOrOptions]
 * @returns {Promise<ReturnType<typeof normalizeMutationResult>>}
 */
export function toggleStar(assetId, stateOrOptions = {}) {
  let starred;
  let fetcher;
  if (typeof stateOrOptions === 'boolean') {
    starred = stateOrOptions;
  } else if (stateOrOptions && typeof stateOrOptions === 'object') {
    if (typeof stateOrOptions.starred === 'boolean') starred = stateOrOptions.starred;
    fetcher = stateOrOptions.fetcher;
  }
  if (typeof starred !== 'boolean') {
    // Without an explicit target we assume the asset is currently unstarred.
    starred = true;
  }
  return starred ? starAsset(assetId, { fetcher }) : unstarAsset(assetId, { fetcher });
}

/* ─────────────────────────────── DOM rendering ─────────────────────────────── */

function createElement(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text != null) el.textContent = text;
  return el;
}

function renderEmptyState(label) {
  const wrap = createElement('div', 'empty-state');
  wrap.append(createElement('strong', null, label));
  return wrap;
}

function renderAssetRow(asset, { starred, onToggle }) {
  const row = createElement('li', 'kairos-quick-access-row');
  const copy = createElement('div', 'kairos-quick-access-copy');
  copy.append(createElement('strong', null, asset.name || asset.qualifiedName || asset.assetId));
  if (asset.qualifiedName && asset.qualifiedName !== asset.name) {
    copy.append(createElement('small', 'small-note', asset.qualifiedName));
  }
  const button = createElement('button', 'btn small kairos-star-toggle', starred ? '★' : '☆');
  button.type = 'button';
  button.dataset.assetId = asset.assetId;
  button.setAttribute('aria-pressed', starred ? 'true' : 'false');
  button.setAttribute('aria-label', starred ? 'Remove star' : 'Star asset');
  button.title = starred ? 'Remove star' : 'Star asset';
  button.addEventListener('click', () => onToggle(asset, !starred, button));
  row.append(copy, button);
  return row;
}

function renderList(slot, state, options) {
  slot.replaceChildren();
  const { title, items, starredIds, onToggle } = options;
  slot.append(createElement('h3', 'kairos-quick-access-title', title));
  if (!items.length) {
    slot.append(renderEmptyState(options.emptyLabel));
    return;
  }
  const list = createElement('ul', 'kairos-quick-access-list');
  for (const asset of items) {
    list.append(renderAssetRow(asset, { starred: starredIds.has(asset.assetId), onToggle }));
  }
  slot.append(list);
  void state;
}

/**
 * Mount the Quick access panel inside `container`.
 *
 * The public API is intentionally small: call this with a container element and
 * optionally a bounded `limit`; it returns a controller exposing `refresh()` and
 * `destroy()`. All DOM is created lazily and every failure (empty list, HTTP
 * error) degrades to a neutral/empty state instead of throwing, so existing
 * views are never broken.
 *
 * @param {HTMLElement} container Target element (must support appendChild).
 * @param {{limit?: number, fetcher?: Function, title?: string}} [options]
 * @returns {{refresh: () => Promise<void>, destroy: () => void, element: HTMLElement} | null}
 */
export function mountPanel(container, options = {}) {
  if (!container || typeof container.appendChild !== 'function' || typeof document === 'undefined') {
    return null;
  }
  const limit = Number.isFinite(Number(options.limit)) && Number(options.limit) > 0 ? Math.floor(Number(options.limit)) : 5;
  const fetcher = options.fetcher;
  const title = options.title || 'Quick access';

  const root = createElement('section', 'panel kairos-quick-access');
  const head = createElement('div', 'panel-head');
  const headCopy = createElement('div');
  headCopy.append(createElement('h2', null, title));
  headCopy.append(createElement('p', null, 'Your recently viewed and starred assets.'));
  head.append(headCopy);
  const body = createElement('div', 'panel-body');
  const recentlySlot = createElement('div', 'kairos-quick-access-slot');
  recentlySlot.dataset.slot = 'recently-viewed';
  const starredSlot = createElement('div', 'kairos-quick-access-slot');
  starredSlot.dataset.slot = 'starred';
  const message = createElement('p', 'small-note kairos-quick-access-message', '');
  message.setAttribute('role', 'status');
  message.setAttribute('aria-live', 'polite');
  body.append(recentlySlot, starredSlot, message);
  root.append(head, body);
  container.appendChild(root);

  const starredIds = new Set();

  const setMessage = (text) => { message.textContent = text || ''; };

  const handleToggle = async (asset, nextStarred, button) => {
    button.disabled = true;
    const result = await toggleStar(asset.assetId, { starred: nextStarred, fetcher });
    button.disabled = false;
    if (result.ok) {
      if (nextStarred) starredIds.add(asset.assetId); else starredIds.delete(asset.assetId);
      button.textContent = nextStarred ? '★' : '☆';
      button.setAttribute('aria-pressed', nextStarred ? 'true' : 'false');
      setMessage(nextStarred ? `Starred ${asset.name || asset.assetId}.` : `Removed star from ${asset.name || asset.assetId}.`);
    } else {
      // Non-blocking: report the failure without throwing or altering the view.
      setMessage(result.error || 'The star could not be updated.');
    }
  };

  const refresh = async () => {
    setMessage('');
    let recently = { items: [], total: 0 };
    let starred = { items: [], total: 0 };
    try {
      [recently, starred] = await Promise.all([
        fetchRecentlyViewed({ limit, fetcher }),
        fetchStarredAssets({ fetcher }),
      ]);
    } catch (error) {
      setMessage(error.message || 'Personalized items are unavailable.');
    }
    starredIds.clear();
    for (const asset of starred.items) starredIds.add(asset.assetId);
    renderList(recentlySlot, {}, {
      title: 'Recently viewed',
      items: recently.items,
      starredIds,
      onToggle: handleToggle,
      emptyLabel: 'No recently viewed assets yet.',
    });
    renderList(starredSlot, {}, {
      title: 'Starred',
      items: starred.items,
      starredIds,
      onToggle: handleToggle,
      emptyLabel: 'No starred assets yet.',
    });
  };

  const destroy = () => { if (root.parentNode) root.parentNode.removeChild(root); };

  refresh().catch(() => setMessage('Personalized items are unavailable.'));

  return { refresh, destroy, element: root };
}

/* ─────────────────────── optional browser self-registration ─────────────────────── */

// Expose the API on the window for consumers that prefer an imperative handle.
// This runs only in a browser; importing the module in Node touches nothing.
if (typeof window !== 'undefined') {
  window.kairosPersonalization = {
    API_BASE,
    buildRecentlyViewedUrl,
    buildRecentlyViewedRecordUrl,
    buildClearRecentlyViewedUrl,
    buildStarredAssetsUrl,
    buildStarUrl,
    normalizeAsset,
    normalizeAssetList,
    normalizeMutationResult,
    fetchRecentlyViewed,
    fetchStarredAssets,
    starAsset,
    unstarAsset,
    toggleStar,
    mountPanel,
  };
}

export default {
  API_BASE,
  buildRecentlyViewedUrl,
  buildRecentlyViewedRecordUrl,
  buildClearRecentlyViewedUrl,
  buildStarredAssetsUrl,
  buildStarUrl,
  normalizeAsset,
  normalizeAssetList,
  normalizeMutationResult,
  fetchRecentlyViewed,
  fetchStarredAssets,
  starAsset,
  unstarAsset,
  toggleStar,
  mountPanel,
};
