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
  it('exposes exactly the three canonical modes', () => {
    expect(Object.values(DATA_MODES)).toEqual(['LIVE', 'IMPORTED', 'DEMO FIXTURE']);
  });
});

describe('isDataMode / normalizeDataMode', () => {
  it('accepts only canonical modes', () => {
    expect(isDataMode(DATA_MODES.LIVE)).toBe(true);
    expect(isDataMode(DATA_MODES.IMPORTED)).toBe(true);
    expect(isDataMode(DATA_MODES.DEMO_FIXTURE)).toBe(true);
    expect(isDataMode('live')).toBe(false);
    expect(isDataMode(undefined)).toBe(false);
  });

  it('fails honest: anything unknown becomes DEMO FIXTURE, never LIVE', () => {
    for (const value of [undefined, null, '', 'connected', 'postgresql', 0, {}]) {
      expect(normalizeDataMode(value)).toBe(DATA_MODES.DEMO_FIXTURE);
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

  it('reports a connected catalog as LIVE', () => {
    expect(resolveDataMode({ dataMode: 'postgresql' })).toBe(DATA_MODES.LIVE);
  });

  it('reports committed import data as IMPORTED', () => {
    expect(resolveDataMode({ dataMode: 'postgresql', hasImportedRun: true }))
      .toBe(DATA_MODES.IMPORTED);
  });

  it('never claims LIVE without a positive connected signal', () => {
    expect(resolveDataMode()).toBe(DATA_MODES.DEMO_FIXTURE);
    expect(resolveDataMode({})).toBe(DATA_MODES.DEMO_FIXTURE);
    expect(resolveDataMode({ dataMode: 'unknown-mode' })).toBe(DATA_MODES.DEMO_FIXTURE);
  });
});

describe('dataModeDescription / dataModeToken', () => {
  it('describes each mode honestly', () => {
    expect(dataModeDescription(DATA_MODES.LIVE)).toMatch(/live/i);
    expect(dataModeDescription(DATA_MODES.IMPORTED)).toMatch(/import/i);
    expect(dataModeDescription(DATA_MODES.DEMO_FIXTURE)).toMatch(/demonstration/i);
  });

  it('returns a DOM-safe token and never throws on bad input', () => {
    expect(dataModeToken(DATA_MODES.LIVE)).toBe('live');
    expect(dataModeToken(DATA_MODES.IMPORTED)).toBe('imported');
    expect(dataModeToken(DATA_MODES.DEMO_FIXTURE)).toBe('demo-fixture');
    expect(dataModeToken(undefined)).toBe('demo-fixture');
    expect(dataModeDescription(undefined)).toMatch(/demonstration/i);
  });
});
