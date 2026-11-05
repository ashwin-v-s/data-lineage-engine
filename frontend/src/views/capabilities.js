/**
 * frontend/src/views/capabilities.js
 * ──────────────────────────────────
 * Pure helpers and the runtime fetcher for the asset capability registry.
 *
 * The UI never hardcodes which tabs or sections an asset page shows: Kairos
 * publishes, per asset, which capabilities it *supports* at all and which are
 * *available for this asset right now*, each with an optional human-readable
 * `reason` when it is not available. This module turns that registry into a
 * stable, ordered shape and — critically — preserves the honest invariant that
 * a capability is reported as available only when it is also supported, and
 * that a reason is present exactly when it is not available.
 *
 * DOM-free and JSX-free so it can be unit-tested in Node.
 */

import { API_BASE, asText, requestJson } from '../api/client.js';

/** The capability vocabulary, in the order the UI presents it. */
export const CAPABILITY_KEYS = ['schema', 'preview', 'lineage', 'runs', 'quality', 'profile', 'usage'];

const FALLBACK_REASON = 'Kairos has not published this capability.';

/**
 * Build the URL for one asset's capability registry.
 * @param {string} assetId Dataset UUID or dataset name.
 * @returns {string}
 */
export function buildCapabilitiesUrl(assetId) {
  return `${API_BASE}/assets/${encodeURIComponent(String(assetId ?? ''))}/capabilities`;
}

/** Coerce any value into a plain (non-array) record, else `null`. */
function asRecordOrNull(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : null;
}

/**
 * Normalise one capability entry.
 *
 * A key that is not part of `CAPABILITY_KEYS`, or a malformed body, degrades to
 * an honest "not published" entry. The invariants are enforced even when the
 * payload violates them: `available` is true only when `supported` is true, and
 * `reason` is `null` if and only if `available` is true.
 *
 * @param {string} key
 * @param {unknown} raw
 * @returns {{key: string, supported: boolean, available: boolean, reason: string|null}}
 */
export function normalizeCapabilityEntry(key, raw) {
  const source = asRecordOrNull(raw);
  if (!CAPABILITY_KEYS.includes(key) || !source) {
    return { key, supported: false, available: false, reason: FALLBACK_REASON };
  }

  const supported = source.supported === true;
  const available = supported && source.available === true;
  if (available) {
    return { key, supported: true, available: true, reason: null };
  }

  const reason = asText(source.reason);
  return { key, supported, available: false, reason: reason || FALLBACK_REASON };
}

/**
 * Normalise a capability registry payload. The returned `capabilities` array
 * always contains all seven keys in `CAPABILITY_KEYS` order, whatever the
 * payload contained.
 * @param {unknown} payload
 * @returns {{assetId: string|null, capabilities: Array, availableKeys: string[], generatedAt: string|null}}
 */
export function normalizeCapabilityRegistry(payload) {
  const source = asRecordOrNull(payload) || {};
  const rawCapabilities = asRecordOrNull(source.capabilities) || {};
  const capabilities = CAPABILITY_KEYS.map((key) => normalizeCapabilityEntry(key, rawCapabilities[key]));
  const availableKeys = capabilities.filter((entry) => entry.available).map((entry) => entry.key);
  return {
    assetId: asText(source.asset_id),
    capabilities,
    availableKeys,
    generatedAt: asText(source.generated_at),
  };
}

/**
 * The subset of a registry the UI is allowed to render as tabs: the available
 * entries only. Safe for a missing/`null` registry.
 * @param {unknown} registry
 * @returns {Array}
 */
export function availableTabs(registry) {
  const source = asRecordOrNull(registry);
  const capabilities = source && Array.isArray(source.capabilities) ? source.capabilities : [];
  return capabilities.filter((entry) => entry && entry.available === true);
}

const LABELS = {
  schema: 'Schema',
  preview: 'Preview',
  lineage: 'Lineage',
  runs: 'Runs',
  quality: 'Quality',
  profile: 'Profile',
  usage: 'Usage',
};

/** A short human label for a capability key. */
export function capabilityLabel(key) {
  return LABELS[key] || (typeof key === 'string' && key ? key : 'Capability');
}

const DESCRIPTIONS = {
  schema: 'The columns and data types Kairos has recorded for this asset.',
  preview: 'A sample of rows derived from the asset\'s stored column metadata.',
  lineage: 'Evidence-backed upstream and downstream relationships.',
  runs: 'Ingestion and execution runs that reference this asset.',
  quality: 'Stored data-quality results and assertions for this asset.',
  profile: 'Statistical column profiling computed for this asset.',
  usage: 'Query-log based usage statistics, which Kairos does not collect.',
};

/** One sentence describing what a capability means. */
export function capabilityDescription(key) {
  return DESCRIPTIONS[key] || 'This capability is not published by Kairos.';
}

/**
 * Fetch the capability registry for one asset. Never throws.
 * @param {string} assetId Dataset UUID or dataset name.
 * @param {{fetcher?: Function}} [options]
 * @returns {Promise<{ok: true, registry: object} | {ok: false, error: string}>}
 */
export async function fetchCapabilities(assetId, { fetcher } = {}) {
  try {
    const data = await requestJson(buildCapabilitiesUrl(assetId), { fetcher });
    return { ok: true, registry: normalizeCapabilityRegistry(data) };
  } catch (error) {
    return { ok: false, error: error.message || 'The asset capabilities could not be loaded.' };
  }
}
