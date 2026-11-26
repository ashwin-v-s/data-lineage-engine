import React, { useCallback, useEffect, useMemo, useState } from 'react';
import DataModeLabel from './DataModeLabel.jsx';
import { DATA_MODES } from './dataMode.js';

/**
 * Trust center — the governance surface every established catalog exposes:
 * certification, discussion, usage popularity and a quality scorecard.
 *
 * Everything shown comes from a persisted API response. A missing metric is
 * rendered as "—", never as a fabricated zero, and a 503 from an unprovisioned
 * migration is explained instead of being replaced with sample rows.
 */

async function request(path, options) {
  const response = await fetch(`/api/v1${path}`, {
    credentials: 'same-origin',
    headers: { Accept: 'application/json', ...(options?.body ? { 'Content-Type': 'application/json' } : {}) },
    ...options,
  });
  let data;
  try { data = await response.json(); } catch (_) { data = {}; }
  if (!response.ok) throw new Error(data?.error?.message || data?.detail || `Request failed (HTTP ${response.status}).`);
  return data;
}

const TABS = [
  ['overview', 'Overview'],
  ['certifications', 'Certifications'],
  ['discussions', 'Discussions'],
];

const STATE_TOKEN = { CERTIFIED: 'ok', EXPIRING: 'warn', EXPIRED: 'bad' };

function percent(value) {
  return typeof value === 'number' && Number.isFinite(value) ? `${Math.round(value * 100)}%` : '—';
}

function when(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

function assetLabel(asset) {
  return asset?.qualified_name || `${asset?.schema_name || asset?.schema || ''}.${asset?.name || ''}`.replace(/^\./, '') || asset?.name || asset?.id;
}

function Stat({ label, value, note }) {
  return (
    <div className="kv-card">
      <p className="kv-label">{label}</p>
      <p style={{ margin: '6px 0 0', font: '800 2rem/1.05 var(--font-display)', color: 'var(--ink)' }}>{value}</p>
      {note ? <p style={{ margin: '8px 0 0' }}>{note}</p> : null}
    </div>
  );
}

export default function TrustView({ demoPreview = false }) {
  const [tab, setTab] = useState('overview');
  const [overview, setOverview] = useState(null);
  const [certifications, setCertifications] = useState([]);
  const [certCounts, setCertCounts] = useState({});
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [connected, setConnected] = useState(false);
  const [selectedAsset, setSelectedAsset] = useState('');
  const [discussion, setDiscussion] = useState(null);
  const [discussionError, setDiscussionError] = useState('');
  const [replyTo, setReplyTo] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setError('');
    if (demoPreview) {
      // The bundle contains no trust fixtures, so the screen states that rather
      // than inventing endorsements or threads.
      setOverview(null);
      setCertifications([]);
      setCertCounts({});
      setAssets([]);
      setConnected(false);
      setLoading(false);
      return;
    }
    try {
      const [summary, register, catalog] = await Promise.all([
        request('/trust/overview'),
        request('/trust/certifications?limit=500'),
        request('/catalog?limit=500'),
      ]);
      setOverview(summary);
      setCertifications(Array.isArray(register.certifications) ? register.certifications : []);
      setCertCounts(register.counts || {});
      setAssets(Array.isArray(catalog.assets) ? catalog.assets : []);
      setConnected(true);
    } catch (err) {
      setOverview(null);
      setCertifications([]);
      setAssets([]);
      setConnected(false);
      setError(err.message || 'Trust data could not be loaded.');
    } finally {
      setLoading(false);
    }
  }, [demoPreview]);

  useEffect(() => { load(); }, [load]);

  const loadDiscussion = useCallback(async (assetId) => {
    setDiscussion(null); setDiscussionError(''); setReplyTo('');
    if (!assetId || demoPreview) return;
    try {
      setDiscussion(await request(`/trust/assets/${encodeURIComponent(assetId)}/discussion`));
    } catch (err) {
      setDiscussionError(err.message || 'The discussion could not be loaded.');
    }
  }, [demoPreview]);

  useEffect(() => { loadDiscussion(selectedAsset); }, [selectedAsset, loadDiscussion]);

  const threads = useMemo(() => {
    const rows = discussion?.comments || [];
    const roots = rows.filter((row) => !row.parent_id);
    return roots.map((root) => ({
      ...root,
      replies: rows.filter((row) => row.parent_id === root.id),
    }));
  }, [discussion]);

  const certify = async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const assetId = String(form.get('asset_id') || '').trim();
    const expires = String(form.get('expires_at') || '').trim();
    setBusy(true); setError(''); setNotice('');
    try {
      await request(`/trust/assets/${encodeURIComponent(assetId)}/certification`, {
        method: 'PUT',
        body: JSON.stringify({
          note: String(form.get('note') || '').trim() || null,
          expires_at: expires ? new Date(expires).toISOString() : null,
        }),
      });
      event.currentTarget.reset();
      setNotice('Certification saved. The endorsement is recorded against your account.');
      await load();
    } catch (err) { setError(err.message || 'The certification could not be saved.'); }
    finally { setBusy(false); }
  };

  const revoke = async (assetId) => {
    setBusy(true); setError(''); setNotice('');
    try {
      await request(`/trust/assets/${encodeURIComponent(assetId)}/certification`, { method: 'DELETE' });
      setNotice('Certification revoked.');
      await load();
    } catch (err) { setError(err.message || 'The certification could not be revoked.'); }
    finally { setBusy(false); }
  };

  const comment = async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true); setError(''); setNotice('');
    try {
      await request(`/trust/assets/${encodeURIComponent(selectedAsset)}/discussion`, {
        method: 'POST',
        body: JSON.stringify({
          body: String(data.get('body') || '').trim(),
          parent_id: String(data.get('parent_id') || '').trim() || null,
        }),
      });
      form.reset();
      setReplyTo('');
      setNotice('Comment posted.');
      await loadDiscussion(selectedAsset);
    } catch (err) { setError(err.message || 'The comment could not be posted.'); }
    finally { setBusy(false); }
  };

  const resolveThread = async (commentId) => {
    setBusy(true); setError(''); setNotice('');
    try {
      await request(`/trust/discussion/${encodeURIComponent(commentId)}/resolve`, { method: 'POST' });
      setNotice('Thread resolved.');
      await loadDiscussion(selectedAsset);
    } catch (err) { setError(err.message || 'The thread could not be resolved.'); }
    finally { setBusy(false); }
  };

  const quality = overview?.quality;
  const summary = quality?.summary;

  return (
    <section className="kv-view kv-freshness-view" aria-labelledby="trustViewTitle">
      <div className="kv-view-head">
        <div>
          <h1 id="trustViewTitle">Trust center</h1>
          <p className="kv-sub">
            Certification, discussion, recorded usage and quality in one place. Certifications are
            steward endorsements; they do not grant access to source data.
          </p>
        </div>
        <div>
          <DataModeLabel mode={demoPreview ? DATA_MODES.DEMO_FIXTURE : connected ? DATA_MODES.LIVE : DATA_MODES.NOT_CONNECTED} />
          <button className="btn" onClick={load} disabled={loading || busy || demoPreview} type="button">Refresh</button>
        </div>
      </div>

      <div className="kv-toolbar" role="tablist" aria-label="Trust center sections">
        {TABS.map(([id, label]) => (
          <button
            key={id}
            aria-selected={tab === id}
            className={`kv-btn${tab === id ? ' kv-btn--primary' : ''}`}
            onClick={() => setTab(id)}
            role="tab"
            type="button"
          >
            {label}
          </button>
        ))}
      </div>

      {demoPreview ? (
        <div className="kv-note">
          This build bundles no trust fixtures, so no certifications, discussions or usage counters are shown.
          Sign in to the live workspace to review persisted records.
        </div>
      ) : null}
      {notice ? <p className="kv-note kv-note--ok" role="status">{notice}</p> : null}
      {error ? (
        <div className="kv-note kv-note--error" role="alert">
          <strong>Trust data unavailable</strong>
          <p>{error}</p>
          <p>No sample certifications or comments are shown in place of an API failure.</p>
        </div>
      ) : null}

      {tab === 'overview' && (
        <>
          <div className="kv-grid">
            <Stat label="Certified assets" value={loading ? '…' : overview?.certification?.certified ?? '—'} note={`${percent(overview?.certification?.coverage)} of the catalog`} />
            <Stat label="Expiring soon" value={loading ? '…' : overview?.certification?.expiring_soon ?? '—'} note="Within the next 30 days" />
            <Stat label="Open discussions" value={loading ? '…' : overview?.discussion?.open_threads ?? '—'} note={`${overview?.discussion?.comments ?? '—'} comments recorded`} />
            <Stat label="Quality pass rate" value={loading ? '…' : percent(summary?.pass_rate)} note={summary ? `${summary.passing} pass · ${summary.failing} fail` : 'No evaluation results yet'} />
          </div>

          <section className="kv-card">
            <h2>Quality scorecard</h2>
            {!quality ? <p className="kv-freshness-placeholder">No scorecard was returned.</p> : (
              <>
                <p>
                  {summary.assertions} enabled assertion{summary.assertions === 1 ? '' : 's'} · {summary.evaluated} evaluated ·{' '}
                  {summary.skipped} skipped · {summary.errored} error · {summary.unevaluated} unevaluated ·{' '}
                  {quality.uncovered_assets} asset{quality.uncovered_assets === 1 ? '' : 's'} with no assertion.
                </p>
                <p className="kv-hint">{quality.semantics}</p>
                {quality.trend.length === 0 ? (
                  <p className="kv-freshness-placeholder">No evaluation was recorded in the last {quality.window_days} days.</p>
                ) : (
                  <div className="kv-table-wrap">
                    <table className="kv-table">
                      <thead><tr><th>Day</th><th>Evaluated</th><th>Passed</th><th>Failed</th><th>Skipped</th><th>Pass rate</th></tr></thead>
                      <tbody>
                        {quality.trend.map((row) => (
                          <tr key={row.day}>
                            <td>{row.day}</td><td>{row.evaluated}</td><td>{row.passed}</td><td>{row.failed}</td>
                            <td>{row.skipped}</td><td>{percent(row.pass_rate)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </section>

          <section className="kv-card">
            <h2>Most opened assets</h2>
            <p className="kv-hint">{overview?.trending_basis || 'Recorded opens are aggregated without user identity.'}</p>
            {!overview || overview.trending.length === 0 ? (
              <p className="kv-freshness-placeholder">No asset has been opened through the workspace yet.</p>
            ) : (
              <div className="kv-table-wrap">
                <table className="kv-table">
                  <thead><tr><th>Asset</th><th>Type</th><th>Recorded opens</th><th>Last opened</th></tr></thead>
                  <tbody>
                    {overview.trending.map((row) => (
                      <tr key={row.asset_id}>
                        <td>{row.qualified_name || row.name}</td>
                        <td>{row.asset_type || '—'}</td>
                        <td>{row.view_count}</td>
                        <td>{when(row.last_viewed_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}

      {tab === 'certifications' && (
        <>
          {!demoPreview && (
            <form className="kv-card kv-freshness-form" onSubmit={certify}>
              <h2>Certify an asset</h2>
              <label>Catalog asset
                <select name="asset_id" required defaultValue="">
                  <option value="" disabled>Choose an asset</option>
                  {assets.map((asset) => <option key={asset.id} value={asset.id}>{assetLabel(asset)} · {asset.asset_type || asset.type}</option>)}
                </select>
              </label>
              <label>Endorsement note
                <input name="note" maxLength={1000} placeholder="What was reviewed and approved" />
              </label>
              <label>Expires (optional)
                <input name="expires_at" type="datetime-local" />
              </label>
              <p>Certification records who endorsed the asset. Expiry is evaluated at read time; an expired endorsement is shown as expired, never silently kept.</p>
              <button className="btn primary" disabled={busy} type="submit">{busy ? 'Saving…' : 'Certify asset'}</button>
            </form>
          )}
          <section className="kv-card">
            <h2>Certification register</h2>
            <p className="kv-hint">{certCounts.CERTIFIED || 0} certified · {certCounts.EXPIRING || 0} expiring · {certCounts.EXPIRED || 0} expired</p>
            {loading ? <p role="status">Loading certifications…</p> : certifications.length === 0 ? (
              <p className="kv-freshness-placeholder">No asset has been certified in this workspace.</p>
            ) : (
              <div className="kv-table-wrap">
                <table className="kv-table">
                  <thead><tr><th>Asset</th><th>State</th><th>Certified by</th><th>Expires</th><th>Note</th><th>Action</th></tr></thead>
                  <tbody>
                    {certifications.map((row) => (
                      <tr key={row.id}>
                        <td>{row.qualified_name || row.dataset_name}</td>
                        <td><span className={`kv-chip kv-chip--${STATE_TOKEN[row.state] || 'muted'}`}>{row.state}</span></td>
                        <td>{row.certified_by_label || '—'}</td>
                        <td>{row.expires_at ? when(row.expires_at) : 'No expiry'}</td>
                        <td>{row.note || '—'}</td>
                        <td>
                          <button className="btn small" disabled={busy || demoPreview} onClick={() => revoke(row.dataset_id)} type="button">Revoke</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}

      {tab === 'discussions' && (
        <section className="kv-card">
          <h2>Asset discussions</h2>
          <div className="kv-freshness-form">
            <label>Catalog asset
              <select value={selectedAsset} onChange={(event) => setSelectedAsset(event.target.value)}>
                <option value="">Choose an asset</option>
                {assets.map((asset) => <option key={asset.id} value={asset.id}>{assetLabel(asset)}</option>)}
              </select>
            </label>
          </div>
          {discussionError ? <p className="kv-note kv-note--error" role="alert">{discussionError}</p> : null}
          {!selectedAsset ? (
            <p className="kv-freshness-placeholder">Choose an asset to read or start a discussion.</p>
          ) : !discussion ? (
            <p role="status">Loading discussion…</p>
          ) : threads.length === 0 ? (
            <p className="kv-freshness-placeholder">No discussion has been recorded for this asset.</p>
          ) : (
            <div style={{ display: 'grid', gap: 14, marginTop: 16 }}>
              {threads.map((thread) => (
                <article key={thread.id} style={{ border: '2px solid var(--ink)', borderRadius: 16, padding: '14px 18px' }}>
                  <div className="kv-toolbar">
                    <strong>{thread.author_label || 'Workspace member'}</strong>
                    <span className="kv-muted">{when(thread.created_at)}</span>
                    <span className={`kv-chip kv-chip--${thread.resolved_at ? 'ok' : 'warn'}`}>{thread.resolved_at ? 'RESOLVED' : 'OPEN'}</span>
                    <span className="kv-spacer" />
                    {!thread.resolved_at && !demoPreview ? (
                      <button className="btn small" disabled={busy} onClick={() => resolveThread(thread.id)} type="button">Resolve</button>
                    ) : null}
                  </div>
                  <p style={{ margin: '10px 0', color: 'var(--ink)', whiteSpace: 'pre-wrap' }}>{thread.body}</p>
                  {thread.replies.map((reply) => (
                    <div key={reply.id} style={{ borderLeft: '3px solid var(--line)', paddingLeft: 12, marginTop: 10 }}>
                      <div className="kv-toolbar">
                        <strong>{reply.author_label || 'Workspace member'}</strong>
                        <span className="kv-muted">{when(reply.created_at)}</span>
                      </div>
                      <p style={{ margin: '6px 0 0', color: 'var(--ink)', whiteSpace: 'pre-wrap' }}>{reply.body}</p>
                    </div>
                  ))}
                  {!demoPreview ? (
                    <button className="btn small" onClick={() => setReplyTo(replyTo === thread.id ? '' : thread.id)} type="button">
                      {replyTo === thread.id ? 'Cancel reply' : 'Reply'}
                    </button>
                  ) : null}
                </article>
              ))}
            </div>
          )}
          {selectedAsset && !demoPreview ? (
            <form className="kv-freshness-form" onSubmit={comment}>
              <h3>{replyTo ? 'Reply to thread' : 'Start a discussion'}</h3>
              <input name="parent_id" type="hidden" value={replyTo} readOnly />
              <label>Comment
                <textarea name="body" maxLength={4000} required placeholder="Ask a question or record a decision" />
              </label>
              <button className="btn primary" disabled={busy} type="submit">{busy ? 'Posting…' : 'Post comment'}</button>
            </form>
          ) : null}
        </section>
      )}
    </section>
  );
}
