import { describe, expect, it } from 'vitest';

import {
  DATA_MODES,
  dataModeDescription,
  dataModeToken,
  isDataMode,
  normalizeDataMode,
  resolveDataMode,
} from '../src/components/dataMode.js';

describe('DATA_MODES', () => {
  it('exposes the complete provenance and unavailable-state vocabulary', () => {
    expect(Object.values(DATA_MODES)).toEqual([
      'LIVE', 'IMPORTED', 'DEMO FIXTURE', 'NOT CONNECTED', 'CATALOG ERROR',
    ]);
  });
});

describe('isDataMode / normalizeDataMode', () => {
  it('accepts only canonical modes', () => {
    expect(isDataMode(DATA_MODES.LIVE)).toBe(true);
    expect(isDataMode(DATA_MODES.IMPORTED)).toBe(true);
    expect(isDataMode('live')).toBe(false);
    expect(isDataMode(undefined)).toBe(false);
  });

  it('normalizes unknown values to the safest unavailable mode', () => {
    for (const value of [undefined, null, '', 'connected', 'postgresql', 0, {}]) {
      expect(normalizeDataMode(value)).toBe(DATA_MODES.NOT_CONNECTED);
    }
  });
});

describe('resolveDataMode', () => {
  it('requires a successful request before reporting a connected catalog as LIVE', () => {
    expect(resolveDataMode({ dataMode: 'postgresql' })).toBe(DATA_MODES.NOT_CONNECTED);
    expect(resolveDataMode({ dataMode: 'postgresql', liveRequestSucceeded: true }))
      .toBe(DATA_MODES.LIVE);
  });

  it('reports committed import data as IMPORTED', () => {
    expect(resolveDataMode({ dataMode: 'postgresql', catalogStatus: 'ready', hasImportedRun: true }))
      .toBe(DATA_MODES.IMPORTED);
  });

  it('defaults unknown modes to NOT CONNECTED, never LIVE', () => {
    expect(resolveDataMode()).toBe(DATA_MODES.NOT_CONNECTED);
    expect(resolveDataMode({})).toBe(DATA_MODES.NOT_CONNECTED);
    expect(resolveDataMode({ dataMode: 'unknown-mode' })).toBe(DATA_MODES.NOT_CONNECTED);
  });
});

describe('dataModeDescription / dataModeToken', () => {
  it('describes each mode honestly', () => {
    expect(dataModeDescription(DATA_MODES.LIVE)).toMatch(/live/i);
    expect(dataModeDescription(DATA_MODES.IMPORTED)).toMatch(/import/i);
  });

  it('returns a DOM-safe token and never throws on bad input', () => {
    expect(dataModeToken(DATA_MODES.LIVE)).toBe('live');
    expect(dataModeToken(DATA_MODES.IMPORTED)).toBe('imported');
    expect(dataModeToken(undefined)).toBe('not-connected');
    expect(dataModeDescription(undefined)).toMatch(/no successful authenticated catalog request/i);
  });
});
