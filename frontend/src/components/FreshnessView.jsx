import React, { useCallback, useEffect, useRef, useState } from 'react';

import DataModeLabel from './DataModeLabel.jsx';
import { DATA_MODES } from './dataMode.js';
import {
  SLA_SIGNALS,
  emptySlaForm,
  fetchFreshness,
  fetchSlas,
  evaluateDataset,
  confirmFreshness,
  formatAge,
  formatTimestamp,
  freshnessChipToken,
  freshnessExplanation,
  upsertSla,
  validateSlaInput,
} from '../views/freshness.js';
import './FreshnessView.css';

const SIGNAL_LABELS = {
  openlineage_run: 'OpenLineage run',
  dbt_run_results: 'dbt run results',
  updated_at: 'Source updated_at',
  manual: 'Manual confirmation',
};

function FreshnessView({ demoPreview = false } = {}) {
  const [evaluations, setEvaluations] = useState([]);
  const [counts, setCounts] = useState({ HEALTHY: 0, AT_RISK: 0, LATE: 0, STALE: 0, UNKNOWN: 0, PAUSED: 0 });
  const [slas, setSlas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [live, setLive] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [form, setForm] = useState(emptySlaForm);
  const [formErrors, setFormErrors] = useState([]);
  const [saving, setSaving] = useState(false);
  const requestVersion = useRef(0);

  const load = useCallback(async ({ quiet = false } = {}) => {
    const version = ++requestVersion.current;
    if (!quiet) setLoading(true);
    setError('');
    if (demoPreview) {
      setEvaluations([]);
      setCounts({ HEALTHY: 0, AT_RISK: 0, LATE: 0, STALE: 0, UNKNOWN: 0, PAUSED: 0 });
      setSlas([]);
      setLive(false);
      setError('Freshness data is unavailable in demo preview. No sample readings are substituted.');
      setLoading(false);
      setRefreshing(false);
      return;
    }
    const [freshnessResult, slaResult] = await Promise.all([fetchFreshness(), fetchSlas()]);
    if (version !== requestVersion.current) return;
    if (!freshnessResult.ok) {
      setEvaluations([]);
      setCounts(freshnessResult.counts);
      setSlas([]);
      setLive(false);
      setError(freshnessResult.error);
    } else {
      setEvaluations(freshnessResult.evaluations);
      setCounts(freshnessResult.counts);
      setLive(true);
      if (slaResult.ok) {
        setSlas(slaResult.slas);
      } else {
        setSlas([]);
        setError(`Freshness readings loaded, but SLA settings could not be loaded: ${slaResult.error}`);
      }
    }
    setLoading(false);
    setRefreshing(false);
  }, [demoPreview]);

  useEffect(() => {
    load();
    return () => { requestVersion.current += 1; };
  }, [load]);

  const refresh = () => {
    setRefreshing(true);
    setNotice('Refreshing the latest stored freshness evaluations. This does not run a new evaluation.');
    load({ quiet: true });
  };

  const saveSla = async (event) => {
    event.preventDefault();
    const validation = validateSlaInput(form);
    setFormErrors(validation.errors);
    setNotice('');
    if (!validation.valid) return;
    setSaving(true);
    const result = await upsertSla({
      ...form,
      warn_after_minutes: Number(form.warn_after_minutes),
      error_after_minutes: Number(form.error_after_minutes),
      stale_after_minutes: form.stale_after_minutes === '' ? null : Number(form.stale_after_minutes),
    });
    setSaving(false);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    setForm(emptySlaForm());
    setFormErrors([]);
    setNotice('Freshness SLA saved. A scheduled evaluation is not configured through this screen.');
    await load({ quiet: true });
  };

  const evaluateNow = async (assetId) => {
    setRefreshing(true);
    setNotice('Running a manual evaluation against stored evidence. This does not contact the source or prove a source run occurred.');
    const result = await evaluateDataset(assetId);
    setRefreshing(false);
    if (!result.ok) setError(result.error);
    else {
      setNotice(`Manual evaluation recorded: ${result.outcome.state}. ${result.outcome.reason || ''}`);
      await load({ quiet: true });
    }
  };

  const submitManualConfirmation = async (event, assetId) => {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    const observed = new Date(String(fields.get('observed_at') || ''));
    if (Number.isNaN(observed.getTime())) { setError('Choose a valid observed-at time.'); return; }
    setRefreshing(true); setError('');
    const result = await confirmFreshness(assetId, { observed_at: observed.toISOString(), note: String(fields.get('note') || '').trim() });
    setRefreshing(false);
    if (!result.ok) setError(result.error);
    else { setNotice('Manual attestation saved. It is labeled MANUAL and is not a runtime observation. Run an evaluation for an SLA configured with the Manual signal.'); form.reset(); }
  };

  return (
    <section className="kv-view kv-freshness-view" aria-labelledby="freshnessTitle">
      <div className="kv-view-head">
        <div>
          <h1 id="freshnessTitle">Freshness</h1>
          <p className="kv-sub">Latest stored evaluations and workspace freshness thresholds.</p>
        </div>
        {live ? <DataModeLabel mode={DATA_MODES.LIVE} /> : demoPreview ? <DataModeLabel mode={DATA_MODES.DEMO_FIXTURE} /> : null}
      </div>

      {notice ? <p className="kv-note" role="status">{notice}</p> : null}
      {error ? <p className="kv-note kv-note--error" role="alert">{error}</p> : null}

      {demoPreview ? (
        <div className="kv-card"><p className="kv-freshness-placeholder">Freshness records are not included in the demo preview. Switch to an authenticated catalog session to load them.</p></div>
      ) : (
        <>
          <section className="kv-card" aria-label="Latest freshness counts">
            <div className="kv-freshness-counts">
              {['HEALTHY', 'AT_RISK', 'LATE', 'STALE', 'UNKNOWN', 'PAUSED'].map((state) => (
                <div className="kv-freshness-count" key={state}>
                  <span>{state.replace('_', ' ')}</span>
                  <strong>{loading ? '—' : counts[state] ?? 0}</strong>
                </div>
              ))}
            </div>
              <p className="kv-freshness-placeholder">UNKNOWN means there is no qualifying source-activity evidence or no configured SLA. Missing evidence is never shown as LATE or STALE. PAUSED is an explicit saved SLA setting.</p>
          </section>

          <section className="kv-card" aria-labelledby="freshnessReadingsTitle">
            <div className="kv-freshness-section-head">
              <div><h2 id="freshnessReadingsTitle">Latest evaluations</h2><p>One latest stored evaluation per asset; this view does not imply a schedule.</p></div>
              <button className="btn" disabled={loading || refreshing} onClick={refresh} type="button">{refreshing ? 'Refreshing…' : 'Refresh readings'}</button>
            </div>
            {loading ? <p className="kv-freshness-placeholder" role="status">Loading freshness records…</p> : evaluations.length === 0 ? (
              <p className="kv-freshness-placeholder">No freshness evaluations were returned by the API.</p>
            ) : (
              <div className="kv-table-wrap">
                <table className="kv-table">
                  <thead><tr><th scope="col">Asset</th><th scope="col">State</th><th scope="col">Age</th><th scope="col">Last source activity</th><th scope="col">Evaluation mode</th><th scope="col">Evidence source</th><th scope="col">Evaluated</th><th scope="col">Action</th></tr></thead>
                  <tbody>{evaluations.map((item) => (
                    <tr key={item.id || item.datasetId}>
                      <td>{item.datasetName || item.datasetId || 'Unknown asset'}</td>
                      <td><span className={`kv-chip kv-chip--${freshnessChipToken(item.displayState)}`} title={item.evidenceConflict ? item.displayReason : freshnessExplanation(item.displayState)}>{item.displayState}</span>{item.evidenceConflict ? <small role="note">{item.displayReason}</small> : null}</td>
                      <td>{formatAge(item.ageMinutes)}</td>
                      <td>{formatTimestamp(item.lastSourceActivityAt)}</td>
                      <td>{item.evaluationMode || 'Unknown'}</td>
                      <td>{item.evidenceSource === 'MANUAL_ATTESTATION' ? <span>MANUAL ATTESTATION · {item.evidenceRef.note || 'Human attestation'} · not runtime evidence</span> : item.evidenceSource === 'RUNTIME' ? <span>RUNTIME · <code>{item.evidenceId}</code></span> : item.evidenceRef?.kind === 'UNAVAILABLE' ? <span>{item.evidenceRef.reason || 'No qualifying evidence reference'}</span> : item.evidenceSource === 'UNVERIFIED' ? <span>Unverified evidence reference{item.evidenceId ? <> · <code>{item.evidenceId}</code></> : ''}</span> : 'No qualifying evidence reference'}</td>
                      <td>{formatTimestamp(item.evaluatedAt)}</td>
                      <td><button className="btn small" disabled={refreshing} onClick={() => evaluateNow(item.datasetId)} type="button">Evaluate now</button><details><summary>Manual confirmation</summary><form onSubmit={(event) => submitManualConfirmation(event, item.datasetId)}><label>Observed at<input name="observed_at" required type="datetime-local" /></label><label>Note<textarea name="note" maxLength={1000} minLength={1} required /></label><button className="btn small" disabled={refreshing} type="submit">Save attestation</button></form></details></td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            )}
          </section>

          <section className="kv-card" aria-labelledby="freshnessSlasTitle">
            <div className="kv-freshness-section-head"><div><h2 id="freshnessSlasTitle">Freshness SLAs</h2><p>Thresholds are workspace-scoped and saved through the authenticated API.</p></div></div>
            {slas.length === 0 ? <p className="kv-freshness-placeholder">No SLA records were returned by the API.</p> : (
              <div className="kv-table-wrap"><table className="kv-table"><thead><tr><th scope="col">Asset</th><th scope="col">Signal</th><th scope="col">Warn</th><th scope="col">SLA</th><th scope="col">Stale</th><th scope="col">Schedule</th><th scope="col">State</th></tr></thead>
                <tbody>{slas.map((sla) => <tr key={sla.id}><td>{sla.datasetName || sla.datasetId || 'Unknown asset'}</td><td>{SIGNAL_LABELS[sla.signal] || sla.signal || 'Unknown'}</td><td>{formatAge(sla.warnAfterMinutes)}</td><td>{formatAge(sla.errorAfterMinutes)}</td><td>{formatAge(sla.staleAfterMinutes)}</td><td>{sla.evaluationSchedule || 'manual'} · {sla.schedulerStatus === 'BLOCKED' ? 'BLOCKED — scheduler adapter unavailable' : 'manual only'}</td><td>{sla.paused ? 'PAUSED' : 'Enabled'}</td></tr>)}</tbody></table></div>
            )}
            <form className="kv-freshness-form" onSubmit={saveSla}>
              <h3>Configure an SLA</h3>
              <label>Asset id or name<input autoComplete="off" onChange={(event) => setForm({ ...form, asset_id: event.target.value })} value={form.asset_id} /></label>
              <label>Signal<select onChange={(event) => setForm({ ...form, signal: event.target.value })} value={form.signal}>{SLA_SIGNALS.map((signal) => <option key={signal} value={signal}>{SIGNAL_LABELS[signal] || signal}</option>)}</select></label>
              <label>SLA duration (minutes)<input min="2" onChange={(event) => { const value = event.target.value; setForm({ ...form, error_after_minutes: value, warn_after_minutes: value ? String(Math.max(1, Math.floor(Number(value) * 0.8))) : '' }); }} type="number" value={form.error_after_minutes} /></label>
              <label>At-risk threshold (80% of SLA)<input disabled min="1" type="number" value={form.warn_after_minutes} readOnly /></label>
              <label>Stale after (minutes, optional)<input min="1" onChange={(event) => setForm({ ...form, stale_after_minutes: event.target.value })} type="number" value={form.stale_after_minutes} /></label>
              <label>Evaluation cadence<select onChange={(event) => setForm({ ...form, evaluation_schedule: event.target.value })} value={form.evaluation_schedule}><option value="manual">Manual</option><option value="15m">Every 15 minutes (scheduler required)</option><option value="hourly">Hourly (scheduler required)</option><option value="daily">Daily (scheduler required)</option></select></label>
              <label><input checked={Boolean(form.paused)} onChange={(event) => setForm({ ...form, paused: event.target.checked })} type="checkbox" /> Pause evaluations</label>
              {formErrors.length ? <ul className="kv-note kv-note--error" role="alert">{formErrors.map((item) => <li key={item.field}>{item.message}</li>)}</ul> : null}
              <button className="btn primary" disabled={saving || loading} type="submit">{saving ? 'Saving…' : 'Save SLA'}</button>
            </form>
          </section>
        </>
      )}
    </section>
  );
}

export default FreshnessView;
