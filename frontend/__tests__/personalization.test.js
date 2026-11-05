import { describe, expect, it } from 'vitest';

import {
  buildClearRecentlyViewedUrl,
  buildRecentlyViewedRecordUrl,
  buildRecentlyViewedUrl,
  buildStarredAssetsUrl,
  buildStarUrl,
  normalizeAssetList,
  normalizeMutationResult,
  toggleStar,
} from '../personalization.js';

/** Build a minimal fetch Response-like stub for the runtime helpers. */
function jsonResponse(body, { ok = true, status = 200 } = {}) {
  return {
    ok,
    status,
    json: async () => body,
  };
}

describe('personalization URL builders', () => {
  it('builds the fixed personalization endpoints', () => {
    expect(buildRecentlyViewedUrl()).toBe('/api/v1/me/recently-viewed');
    expect(buildStarredAssetsUrl()).toBe('/api/v1/me/starred-assets');
    expect(buildClearRecentlyViewedUrl()).toBe('/api/v1/me/recently-viewed');
  });

  it('appends a valid limit and omits invalid ones', () => {
    expect(buildRecentlyViewedUrl(10)).toBe('/api/v1/me/recently-viewed?limit=10');
    expect(buildRecentlyViewedUrl('25')).toBe('/api/v1/me/recently-viewed?limit=25');
    expect(buildRecentlyViewedUrl('nope')).toBe('/api/v1/me/recently-viewed');
    expect(buildRecentlyViewedUrl(-3)).toBe('/api/v1/me/recently-viewed');
  });

  it('encodes asset ids in the record and star URLs', () => {
    expect(buildRecentlyViewedRecordUrl('asset 1')).toBe('/api/v1/me/recently-viewed/asset%201');
    expect(buildStarUrl('a/b')).toBe('/api/v1/assets/a%2Fb/star');
    expect(buildStarUrl('')).toBe('/api/v1/assets//star');
  });
});

describe('normalizeAssetList', () => {
  it('normalises a well-formed list and preserves total', () => {
    const result = normalizeAssetList({
      items: [
        {
          asset_id: '11111111-2222-3333-4444-555555555555',
          name: 'orders',
          asset_type: 'TABLE',
          schema_name: 'commerce',
          database_name: 'warehouse',
          source_system: 'postgres',
          qualified_name: 'warehouse.commerce.orders',
          recorded_at: '2026-01-01T00:00:00Z',
        },
      ],
      total: 42,
    });
    expect(result.total).toBe(42);
    expect(result.items).toHaveLength(1);
    expect(result.items[0]).toEqual({
      assetId: '11111111-2222-3333-4444-555555555555',
      name: 'orders',
      assetType: 'TABLE',
      schemaName: 'commerce',
      databaseName: 'warehouse',
      sourceSystem: 'postgres',
      qualifiedName: 'warehouse.commerce.orders',
      recordedAt: '2026-01-01T00:00:00Z',
    });
  });

  it('returns an empty neutral state for an empty list', () => {
    expect(normalizeAssetList({ items: [], total: 0 })).toEqual({ items: [], total: 0 });
  });

  it('degrades malformed payloads to an empty list without throwing', () => {
    expect(normalizeAssetList(null)).toEqual({ items: [], total: 0 });
    expect(normalizeAssetList('not-an-object')).toEqual({ items: [], total: 0 });
    // `items` present but not an array -> empty items, while a finite total is kept.
    expect(normalizeAssetList({ items: 'oops', total: 7 })).toEqual({ items: [], total: 7 });
    // No usable total -> fall back to the number of normalised items.
    expect(normalizeAssetList({ items: 'oops' })).toEqual({ items: [], total: 0 });
  });

  it('drops item entries that are malformed or missing an id', () => {
    const result = normalizeAssetList({
      items: [
        null,
        'bad-entry',
        { name: 'no id here' },
        { qualified_name: 'warehouse.commerce.orders' },
      ],
    });
    // Only the entry with a resolvable id survives, using qualified_name as fallback.
    expect(result.items).toHaveLength(1);
    expect(result.items[0].assetId).toBe('warehouse.commerce.orders');
    expect(result.total).toBe(1);
  });
});

describe('normalizeMutationResult', () => {
  it('normalises a well-formed mutation result', () => {
    expect(normalizeMutationResult({ ok: true, asset_id: 'abc', starred: true })).toEqual({
      ok: true,
      assetId: 'abc',
      starred: true,
      deleted: null,
      error: null,
    });
  });

  it('defaults missing fields on a malformed result', () => {
    expect(normalizeMutationResult(undefined)).toEqual({
      ok: false,
      assetId: null,
      starred: null,
      deleted: null,
      error: null,
    });
    expect(normalizeMutationResult({ ok: true, deleted: 4 }).deleted).toBe(4);
  });
});

describe('toggleStar', () => {
  it('uses POST to star and DELETE to unstar', async () => {
    const calls = [];
    const fetcher = async (url, options) => {
      calls.push({ url, method: options.method });
      return jsonResponse({ ok: true, asset_id: 'abc', starred: options.method === 'POST' });
    };

    const starred = await toggleStar('abc', { starred: true, fetcher });
    const unstarred = await toggleStar('abc', { starred: false, fetcher });

    expect(calls).toEqual([
      { url: '/api/v1/assets/abc/star', method: 'POST' },
      { url: '/api/v1/assets/abc/star', method: 'DELETE' },
    ]);
    expect(starred).toMatchObject({ ok: true, assetId: 'abc', starred: true });
    expect(unstarred).toMatchObject({ ok: true, assetId: 'abc', starred: false });
  });

  it('surfaces a failure as a non-blocking result instead of throwing', async () => {
    const fetcher = async () => jsonResponse({ detail: 'Asset not found.' }, { ok: false, status: 404 });
    const result = await toggleStar('missing', { starred: true, fetcher });
    expect(result.ok).toBe(false);
    expect(result.starred).toBeNull();
    expect(result.error).toBe('Asset not found.');
  });
});
