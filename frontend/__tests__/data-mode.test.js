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
  it('exposes the shared provenance modes, including a failed-request mode', () => {
    expect(Object.values(DATA_MODES)).toEqual([
      'LIVE',
      'IMPORTED',
      'DEMO FIXTURE',
      'NOT CONNECTED',
      'CATALOG ERROR',
    ]);
  });
});

describe('isDataMode / normalizeDataMode', () => {
  it('accepts only canonical modes', () => {
    expect(isDataMode(DATA_MODES.LIVE)).toBe(true);
    expect(isDataMode(DATA_MODES.IMPORTED)).toBe(true);
    expect(isDataMode(DATA_MODES.DEMO_FIXTURE)).toBe(true);
    expect(isDataMode(DATA_MODES.NOT_CONNECTED)).toBe(true);
    expect(isDataMode(DATA_MODES.ERROR)).toBe(true);
    expect(isDataMode('live')).toBe(false);
    expect(isDataMode(undefined)).toBe(false);
  });

  it('fails honest: anything unknown becomes NOT CONNECTED, never LIVE', () => {
    for (const value of [undefined, null, '', 'connected', 'postgresql', 0, {}]) {
      expect(normalizeDataMode(value)).toBe(DATA_MODES.NOT_CONNECTED);
    }
  });
});

describe('resolveDataMode', () => {
  it('reports a demo preview as DEMO FIXTURE', () => {
    expect(resolveDataMode({ dataMode: 'postgresql', demoPreview: true }))
      .toBe(DATA_MODES.DEMO_FIXTURE);
  });

  it('reports the demo data mode as DEMO FIXTURE', () => {
    expect(resolveDataMode({ dataMode: 'demo' })).toBe(DATA_MODES.DEMO_FIXTURE);
  });

  it('does not call a selected catalog LIVE before an authenticated request succeeds', () => {
    expect(resolveDataMode({ dataMode: 'postgresql' })).toBe(DATA_MODES.NOT_CONNECTED);
    expect(resolveDataMode({ dataMode: 'postgresql', liveRequestSucceeded: false }))
      .toBe(DATA_MODES.NOT_CONNECTED);
  });

  it('reports a catalog as LIVE only after an authenticated request succeeds', () => {
    expect(resolveDataMode({ dataMode: 'postgresql', liveRequestSucceeded: true }))
      .toBe(DATA_MODES.LIVE);
  });

  it('reports committed import data as IMPORTED', () => {
    expect(resolveDataMode({ dataMode: 'postgresql', liveRequestSucceeded: true, hasImportedRun: true }))
      .toBe(DATA_MODES.IMPORTED);
    expect(resolveDataMode({ dataMode: 'postgresql', hasImportedRun: true }))
      .toBe(DATA_MODES.NOT_CONNECTED);
  });

  it('never claims LIVE without a positive connected signal', () => {
    expect(resolveDataMode()).toBe(DATA_MODES.NOT_CONNECTED);
    expect(resolveDataMode({})).toBe(DATA_MODES.NOT_CONNECTED);
    expect(resolveDataMode({ dataMode: 'unknown-mode' })).toBe(DATA_MODES.NOT_CONNECTED);
  });

  describe('catalogStatus (dashboard caller)', () => {
    it('reports a failed authenticated request as CATALOG ERROR, not as LIVE or empty', () => {
      expect(resolveDataMode({ dataMode: 'postgresql', catalogStatus: 'error' }))
        .toBe(DATA_MODES.ERROR);
      expect(resolveDataMode({ dataMode: 'postgresql', catalogStatus: 'error', hasImportedRun: true }))
        .toBe(DATA_MODES.ERROR);
    });

    it('keeps loading and unknown statuses at NOT CONNECTED', () => {
      for (const catalogStatus of ['loading', 'idle', 'partial', '', null]) {
        expect(resolveDataMode({ dataMode: 'postgresql', catalogStatus }))
          .toBe(DATA_MODES.NOT_CONNECTED);
      }
    });

    it('reports LIVE only for an explicit ready status', () => {
      expect(resolveDataMode({ dataMode: 'postgresql', catalogStatus: 'ready' }))
        .toBe(DATA_MODES.LIVE);
      expect(resolveDataMode({ dataMode: 'postgresql', catalogStatus: 'ready', hasImportedRun: true }))
        .toBe(DATA_MODES.IMPORTED);
    });

    it('keeps a demo preview ahead of any catalog status', () => {
      expect(resolveDataMode({ dataMode: 'postgresql', demoPreview: true, catalogStatus: 'error' }))
        .toBe(DATA_MODES.DEMO_FIXTURE);
      expect(resolveDataMode({ dataMode: 'demo', demoPreview: true, catalogStatus: 'ready' }))
        .toBe(DATA_MODES.DEMO_FIXTURE);
    });
  });
});

describe('dataModeDescription / dataModeToken', () => {
  it('describes each mode honestly', () => {
    expect(dataModeDescription(DATA_MODES.LIVE)).toMatch(/live/i);
    expect(dataModeDescription(DATA_MODES.IMPORTED)).toMatch(/import/i);
    expect(dataModeDescription(DATA_MODES.DEMO_FIXTURE)).toMatch(/demonstration/i);
    expect(dataModeDescription(DATA_MODES.NOT_CONNECTED)).toMatch(/no successful authenticated catalog request/i);
    expect(dataModeDescription(DATA_MODES.ERROR)).toMatch(/failed/i);
  });

  it('returns a DOM-safe token and never throws on bad input', () => {
    expect(dataModeToken(DATA_MODES.LIVE)).toBe('live');
    expect(dataModeToken(DATA_MODES.IMPORTED)).toBe('imported');
    expect(dataModeToken(DATA_MODES.DEMO_FIXTURE)).toBe('demo-fixture');
    expect(dataModeToken(DATA_MODES.NOT_CONNECTED)).toBe('not-connected');
    expect(dataModeToken(DATA_MODES.ERROR)).toBe('error');
    expect(dataModeToken(undefined)).toBe('not-connected');
    expect(dataModeDescription(undefined)).toMatch(/no successful authenticated catalog request/i);
  });
});
