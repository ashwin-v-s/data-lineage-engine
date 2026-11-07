import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import {
  emptySlaForm,
  fetchFreshness,
  formatAge,
  freshnessExplanation,
  normalizeEvaluation,
  normalizeFreshnessPayload,
  normalizeSla,
  validateSlaInput,
} from '../src/views/freshness.js';

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const freshnessComponent = readFileSync(resolve(frontendRoot, 'src/components/FreshnessView.jsx'), 'utf8');

function makeRuntimeEvaluation({ state = 'LATE', completedAt = '2026-11-01T10:00:00Z', activityAt } = {}) {
  return {
    state,
    age_minutes: 91,
    evidence_id: 'runtime-evidence-1',
    ...(activityAt === undefined ? {} : { last_source_activity_at: activityAt }),
    evidence_ref: {
      kind: 'SUCCESSFUL_RUNTIME_EVIDENCE',
      source_system: 'openlineage',
      evidence_type: 'RUNTIME_POSITIVE',
      evidence_id: 'runtime-evidence-1',
      run_id: 'run-1',
      run_status: 'completed',
      completed_at: completedAt,
    },
  };
}

describe('freshness view contract', () => {
  it('keeps missing evidence UNKNOWN and does not invent age', () => {
    const result = normalizeFreshnessPayload({
      evaluations: [{ state: 'UNKNOWN', age_minutes: null, last_source_activity_at: null }],
    });

    expect(result.evaluations[0].state).toBe('UNKNOWN');
    expect(result.evaluations[0].ageMinutes).toBeNull();
    expect(result.counts.UNKNOWN).toBe(1);
    expect(freshnessExplanation('UNKNOWN')).toMatch(/no source activity/i);
  });

  it('validates SLA thresholds before sending an authenticated write', () => {
    const valid = { ...emptySlaForm(), asset_id: 'dataset-id' };
    expect(validateSlaInput(valid)).toEqual({ valid: true, errors: [] });
    expect(validateSlaInput({ ...valid, error_after_minutes: valid.warn_after_minutes }))
      .toMatchObject({ valid: false });
    expect(validateSlaInput({ ...valid, warn_after_minutes: 0 })).toMatchObject({ valid: false });
  });

  it('does not display a missing age as a fabricated duration', () => {
    expect(formatAge(null)).toBe('—');
    expect(formatAge(-1)).toBe('—');
  });

  it('labels configured nonmanual cadence as blocked until scheduler adapter exists', () => {
    expect(normalizeSla({ evaluation_schedule: '15m' })).toMatchObject({
      evaluationSchedule: '15m',
      schedulerStatus: 'BLOCKED',
    });
    expect(normalizeSla({ evaluation_schedule: 'manual' }).schedulerStatus).toBe('MANUAL');
  });

  it('loads and renders a persisted evaluation from the authenticated API response', async () => {
    const requests = [];
    const result = await fetchFreshness({
      fetcher: async (url, options) => {
        requests.push({ url, options });
        return {
          ok: true,
          json: async () => ({
            evaluations: [{
              id: 'evaluation-42',
              dataset_id: 'asset-42',
              dataset_name: 'orders_daily',
              state: 'LATE',
              age_minutes: 91,
              evidence_id: 'evidence-17',
              last_source_activity_at: '2026-11-01T10:00:00Z',
              evidence_ref: {
                kind: 'SUCCESSFUL_RUNTIME_EVIDENCE',
                source_system: 'openlineage',
                evidence_type: 'RUNTIME_POSITIVE',
                evidence_id: 'evidence-17',
                run_id: 'run-17',
                run_status: 'completed',
                completed_at: '2026-11-01T10:00:00Z',
              },
              evaluation_mode: 'MANUAL',
              reason: 'Last completed runtime was outside the SLA.',
            }],
            counts: { LATE: 1 },
            total: 1,
          }),
        };
      },
    });

    expect(requests).toHaveLength(1);
    expect(requests[0].url).toBe('/api/v1/governance/freshness');
    expect(requests[0].options).toMatchObject({ method: 'GET', credentials: 'same-origin' });
    expect(result).toMatchObject({
      ok: true,
      total: 1,
      evaluations: [{
        id: 'evaluation-42',
        datasetId: 'asset-42',
        datasetName: 'orders_daily',
        state: 'LATE',
        displayState: 'LATE',
        ageMinutes: 91,
        evidenceId: 'evidence-17',
        evaluationMode: 'MANUAL',
      }],
    });

    // This project has no DOM-rendering test dependency. Assert the existing
    // view consumes the fetched records and binds displayed cells to those
    // normalized API fields rather than to sample fixtures.
    expect(freshnessComponent).toContain('setEvaluations(freshnessResult.evaluations)');
    expect(freshnessComponent).toContain('evaluations.map((item) => (');
    expect(freshnessComponent).toContain('{item.datasetName || item.datasetId ||');
    expect(freshnessComponent).toContain('{item.displayState}</span>');
    expect(freshnessComponent).toContain('{formatAge(item.ageMinutes)}');
    expect(freshnessComponent).toContain("item.evidenceSource === 'RUNTIME'");
  });

  it.each(['LATE', 'STALE'])('shows persisted %s as unconfirmed when evidence is explicitly unavailable', (state) => {
    const evaluation = normalizeEvaluation({
      state,
      age_minutes: 90,
      evidence_id: null,
      evidence_ref: { kind: 'UNAVAILABLE', reason: 'No supported evidence signal was found.' },
      evaluation_mode: 'MANUAL',
    });

    expect(evaluation).toMatchObject({
      state,
      ageMinutes: 90,
      evidenceId: null,
      evidenceRef: { kind: 'UNAVAILABLE' },
      evaluationMode: 'MANUAL',
      displayState: 'UNKNOWN',
      evidenceConflict: true,
    });
    expect(evaluation.displayReason).toMatch(/stored .* verdict conflicts with its evidence/i);
  });

  it.each(['LATE', 'STALE'])('preserves a %s verdict backed by completed runtime evidence', (state) => {
    const evaluation = normalizeEvaluation(makeRuntimeEvaluation({ state }));

    expect(evaluation).toMatchObject({ state, displayState: state, evidenceConflict: false, evidenceSource: 'RUNTIME' });
  });

  it.each([
    '2026-02-30T10:00:00Z',
    '2026-02-29T10:00:00Z',
  ])('rejects impossible runtime calendar date %s', (completedAt) => {
    const evaluation = normalizeEvaluation(makeRuntimeEvaluation({ completedAt }));

    expect(evaluation.displayState).toBe('UNKNOWN');
    expect(evaluation.evidenceConflict).toBe(true);
  });

  it('accepts a valid leap-day timestamp', () => {
    const evaluation = normalizeEvaluation(makeRuntimeEvaluation({ completedAt: '2024-02-29T10:00:00Z' }));

    expect(evaluation).toMatchObject({ displayState: 'LATE', evidenceSource: 'RUNTIME', evidenceConflict: false });
  });

  it.each([
    '2026-11-01T10:00:00Z',
    '2026-11-01T10:00:00+00:00',
    '2026-11-01T15:30:00.123456+05:30',
  ])('preserves a supported valid runtime timestamp format: %s', (completedAt) => {
    const evaluation = normalizeEvaluation(makeRuntimeEvaluation({ completedAt }));

    expect(evaluation.displayState).toBe('LATE');
    expect(evaluation.evidenceSource).toBe('RUNTIME');
  });

  it('accepts activity and completion timestamps that represent the same instant', () => {
    const evaluation = normalizeEvaluation(makeRuntimeEvaluation({
      completedAt: '2026-11-01T10:00:00.123456Z',
      activityAt: '2026-11-01T15:30:00.123456+05:30',
    }));

    expect(evaluation).toMatchObject({ displayState: 'LATE', evidenceSource: 'RUNTIME', evidenceConflict: false });
  });

  it('shows UNKNOWN when activity and completion timestamps conflict', () => {
    const evaluation = normalizeEvaluation(makeRuntimeEvaluation({ activityAt: '2026-11-01T10:00:01Z' }));

    expect(evaluation).toMatchObject({ state: 'LATE', displayState: 'UNKNOWN', evidenceConflict: true });
  });

  it('shows UNKNOWN when a provided activity timestamp is invalid', () => {
    const evaluation = normalizeEvaluation(makeRuntimeEvaluation({ activityAt: '2026-02-30T10:00:00Z' }));

    expect(evaluation).toMatchObject({ state: 'LATE', displayState: 'UNKNOWN', evidenceConflict: true });
  });

  it('does not require the optional activity timestamp when the runtime reference is complete', () => {
    const evaluation = normalizeEvaluation(makeRuntimeEvaluation());

    expect(evaluation).toMatchObject({ displayState: 'LATE', evidenceSource: 'RUNTIME', evidenceConflict: false });
  });

  it('preserves a LATE verdict backed by manual attestation as non-runtime evidence', () => {
    const evaluation = normalizeEvaluation({
      state: 'LATE',
      age_minutes: 91,
      last_source_activity_at: '2026-11-01T10:00:00Z',
      evidence_ref: {
        kind: 'MANUAL_CONFIRMATION',
        confirmation_id: 'confirmation-1',
        confirmed_by: 'user-1',
        note: 'Confirmed by data owner',
        recorded_at: '2026-11-01T10:05:00Z',
      },
      evaluation_mode: 'MANUAL',
    });

    expect(evaluation).toMatchObject({ state: 'LATE', displayState: 'LATE', evidenceConflict: false, evidenceSource: 'MANUAL_ATTESTATION' });
    expect(freshnessComponent).toContain('MANUAL ATTESTATION');
    expect(freshnessComponent).toContain('not runtime evidence');
  });

  it.each([
    ['missing evidence reference', { evidence_id: null, evidence_ref: null }],
    ['incomplete runtime evidence reference', {
      evidence_id: 'runtime-evidence-2',
      evidence_ref: { kind: 'SUCCESSFUL_RUNTIME_EVIDENCE', run_id: 'run-2', run_status: 'running' },
    }],
    ['malformed runtime completion timestamp', {
      evidence_id: 'runtime-evidence-4',
      evidence_ref: {
        kind: 'SUCCESSFUL_RUNTIME_EVIDENCE', source_system: 'openlineage', evidence_type: 'RUNTIME_POSITIVE',
        evidence_id: 'runtime-evidence-4', run_id: 'run-4', run_status: 'completed', completed_at: 'not-a-date',
      },
    }],
    ['non-ISO runtime completion timestamp', {
      evidence_id: 'runtime-evidence-5',
      evidence_ref: {
        kind: 'SUCCESSFUL_RUNTIME_EVIDENCE', source_system: 'openlineage', evidence_type: 'RUNTIME_POSITIVE',
        evidence_id: 'runtime-evidence-5', run_id: 'run-5', run_status: 'completed', completed_at: '1',
      },
    }],
    ['incomplete manual confirmation reference', {
      evidence_ref: { kind: 'MANUAL_CONFIRMATION', confirmation_id: 'confirmation-2' },
    }],
  ])('keeps a breach unconfirmed with %s', (_caseName, evidence) => {
    const evaluation = normalizeEvaluation({ state: 'LATE', age_minutes: 120, ...evidence });

    expect(evaluation.state).toBe('LATE');
    expect(evaluation.displayState).toBe('UNKNOWN');
    expect(evaluation.evidenceConflict).toBe(true);
    expect(evaluation.evidenceSource).toBe('UNVERIFIED');
  });

  it('does not infer REFUTED_FOR_RUN from missing evidence and preserves API UNKNOWN', () => {
    const evaluation = normalizeEvaluation({
      state: 'UNKNOWN',
      age_minutes: null,
      evidence_id: null,
      evidence_ref: { kind: 'UNAVAILABLE' },
    });

    expect(evaluation).toMatchObject({ state: 'UNKNOWN', displayState: 'UNKNOWN', ageMinutes: null });
    expect(evaluation.displayState).not.toBe('REFUTED_FOR_RUN');
  });

  it('preserves an unrecognized persisted state while presenting it as UNKNOWN', () => {
    const evaluation = normalizeEvaluation({ state: 'REFUTED_FOR_RUN' });

    expect(evaluation.state).toBe('REFUTED_FOR_RUN');
    expect(evaluation.displayState).toBe('UNKNOWN');
  });

  it('derives summary counts from effective display states', () => {
    const result = normalizeFreshnessPayload({
      evaluations: [
        { state: 'LATE', age_minutes: 100, evidence_ref: { kind: 'UNAVAILABLE' } },
        { state: 'LATE', age_minutes: 100, evidence_id: 'runtime-evidence-3', evidence_ref: {
          kind: 'SUCCESSFUL_RUNTIME_EVIDENCE', source_system: 'openlineage', evidence_type: 'RUNTIME_POSITIVE',
          evidence_id: 'runtime-evidence-3', run_id: 'run-3', run_status: 'completed', completed_at: '2026-11-01T10:00:00Z',
        } },
        { state: 'UNKNOWN', age_minutes: null, evidence_ref: { kind: 'UNAVAILABLE' } },
      ],
      counts: { LATE: 2, UNKNOWN: 1 },
    });

    expect(result.counts).toMatchObject({ LATE: 1, UNKNOWN: 2, STALE: 0 });
    expect(result.evaluations.map((item) => item.displayState)).toEqual(['UNKNOWN', 'LATE', 'UNKNOWN']);
  });

  it('preserves UNKNOWN from the persisted API when source evidence is insufficient', () => {
    const result = normalizeFreshnessPayload({
      evaluations: [{
        id: 'evaluation-unknown',
        dataset_id: 'asset-unknown',
        state: 'UNKNOWN',
        age_minutes: null,
        evidence_ref: { kind: 'UNAVAILABLE' },
      }],
    });

    expect(result.evaluations[0]).toMatchObject({
      state: 'UNKNOWN',
      ageMinutes: null,
      evidenceRef: { kind: 'UNAVAILABLE' },
    });
    expect(result.counts.UNKNOWN).toBe(1);
    expect(result.counts.LATE).toBe(0);
    expect(result.counts.STALE).toBe(0);
    expect(freshnessComponent).toContain('UNKNOWN means there is no qualifying source-activity evidence');
  });

  it('displays evaluation mode separately from evidence source', () => {
    const manual = normalizeEvaluation({ state: 'HEALTHY', evaluation_mode: 'MANUAL' });
    const scheduled = normalizeEvaluation({ state: 'HEALTHY', evaluation_mode: 'SCHEDULED' });

    expect(manual.evaluationMode).toBe('MANUAL');
    expect(scheduled.evaluationMode).toBe('SCHEDULED');
    expect(freshnessComponent).toMatch(/item\.evaluationMode/);
    expect(freshnessComponent).toContain('<th scope="col">Evaluation mode</th>');
    expect(freshnessComponent).toContain('<th scope="col">Evidence source</th>');
    expect(freshnessComponent).toContain('· not runtime evidence');
  });

  it('keeps scheduled freshness visibly blocked in the SLA table', () => {
    const sla = normalizeSla({ evaluation_schedule: 'hourly', scheduler_status: 'BLOCKED' });

    expect(sla).toMatchObject({ evaluationSchedule: 'hourly', schedulerStatus: 'BLOCKED' });
    expect(freshnessComponent).toContain('sla.schedulerStatus === \'BLOCKED\'');
    expect(freshnessComponent).toContain('BLOCKED — scheduler adapter unavailable');
  });

  it('shows an authenticated API failure without substituting fixture readings', async () => {
    const result = await fetchFreshness({
      fetcher: async () => ({
        ok: false,
        status: 503,
        json: async () => ({ detail: 'Governance storage is unavailable.' }),
      }),
    });

    expect(result).toMatchObject({ ok: false, evaluations: [], total: 0 });
    expect(result.error).toBe('Governance storage is unavailable.');
    expect(freshnessComponent).toContain('setEvaluations([])');
    expect(freshnessComponent).toContain('setError(freshnessResult.error)');
    expect(freshnessComponent).toContain('No sample readings are substituted.');
  });
});
