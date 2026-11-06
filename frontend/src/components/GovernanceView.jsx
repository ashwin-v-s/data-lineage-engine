import React, { useCallback, useEffect, useState } from 'react';
import DataModeLabel from './DataModeLabel.jsx';
import { DATA_MODES } from './dataMode.js';

const VIEWS = {
  sources: { title: 'Sources & connections', endpoint: '/sources', key: '__array' },
  settings: { title: 'Settings & workspace members', endpoint: '/members', key: 'members' },
  glossary: { title: 'Glossary', endpoint: '/governance/terms', key: 'terms' },
  pii: { title: 'PII classification', endpoint: '/governance/classifications', key: 'classifications' },
  domains: { title: 'Domains', endpoint: '/governance/domains', key: 'domains' },
  products: { title: 'Data products', endpoint: '/governance/products', key: 'products' },
  quality: { title: 'Data quality', endpoint: '/quality/assertions', key: 'assertions' },
  notifications: { title: 'Notifications', endpoint: '/notifications', key: 'notifications' },
};
const NOTIFICATION_TYPES = ['FRESHNESS_BREACH', 'QUALITY_FAILURE', 'INCIDENT_CREATED', 'SYNC_FAILURE', 'CREDENTIAL_EXPIRY', 'LINEAGE_CHANGE', 'PII_CHANGE'];

async function request(path, options) {
  const response = await fetch(`/api/v1${path}`, { credentials: 'same-origin', headers: { Accept: 'application/json', ...(options?.body ? { 'Content-Type': 'application/json' } : {}) }, ...options });
  let data;
  try { data = await response.json(); } catch (_) { data = {}; }
  if (!response.ok) throw new Error(data?.error?.message || data?.detail || `Request failed (HTTP ${response.status}).`);
  return data;
}

export default function GovernanceView({ view, demoPreview = false }) {
  const config = VIEWS[view] || VIEWS.glossary;
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [connected, setConnected] = useState(false);
  const [preferences, setPreferences] = useState([]);
  const [preferencesError, setPreferencesError] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setError('');
    if (demoPreview) { setRows([]); setError('Governance records are not included in demo preview. No sample rows are substituted.'); setLoading(false); return; }
    try {
      const data = await request(config.endpoint);
      setRows(config.key === '__array' ? (Array.isArray(data) ? data : []) : Array.isArray(data[config.key]) ? data[config.key] : []);
      if (view === 'settings') {
        try {
          const prefData = await request('/notifications/preferences');
          setPreferences(Array.isArray(prefData.preferences) ? prefData.preferences : []);
          setPreferencesError('');
        } catch (prefErr) { setPreferencesError(prefErr.message || 'Notification preference storage is unavailable.'); }
      }
      setConnected(true);
    } catch (err) { setRows([]); setConnected(false); setError(err.message || 'Governance data could not be loaded.'); }
    finally { setLoading(false); }
  }, [config, demoPreview, view]);

  useEffect(() => { load(); }, [load]);

  const submit = async (event) => {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setBusy(true); setError(''); setNotice('');
    try {
      let path = config.endpoint; let body;
      if (view === 'glossary') body = { name: String(form.get('name') || '').trim(), definition: String(form.get('definition') || '').trim() };
      else if (view === 'pii') {
        const classification = String(form.get('classification') || 'PII_SOURCE');
        const origin = classification === 'PII_INHERITED' ? 'inherited_lineage' : classification === 'PII_POTENTIAL' ? 'sqlglot_possible' : 'manual_steward';
        body = { dataset_id: String(form.get('dataset_id') || '').trim(), column_id: String(form.get('column_id') || '').trim() || null, classification, evidence_state: String(form.get('evidence_state') || 'OBSERVED'), provenance: { origin, note: String(form.get('provenance_note') || '').trim() } };
      }
      else if (view === 'domains') body = { name: String(form.get('name') || '').trim(), description: String(form.get('description') || '').trim() };
      else if (view === 'products') body = { name: String(form.get('name') || '').trim(), description: String(form.get('description') || '').trim(), status: 'DRAFT', asset_ids: String(form.get('asset_ids') || '').split(',').map((value) => value.trim()).filter(Boolean) };
      else if (view === 'quality') body = { dataset_id: String(form.get('dataset_id') || '').trim(), name: String(form.get('name') || '').trim(), assertion_type: String(form.get('assertion_type') || 'completeness'), definition: {}, severity: String(form.get('severity') || 'MEDIUM'), schedule: 'manual' };
      else if (view === 'settings') { path = '/members/invites'; body = { email: String(form.get('email') || '').trim(), role: String(form.get('role') || 'viewer') }; }
      else if (view === 'sources') body = { name: String(form.get('name') || '').trim(), source_kind: 'postgresql', host: String(form.get('host') || '').trim(), port: Number(form.get('port') || 5432), dbname: String(form.get('dbname') || '').trim(), user: String(form.get('user') || '').trim(), password: String(form.get('password') || ''), schema_name: String(form.get('schema_name') || 'public').trim() };
      else throw new Error('This screen has no create action available.');
      await request(path, { method: 'POST', body: JSON.stringify(body) });
      formElement.reset(); setNotice(`${config.title} record saved.`); await load();
    } catch (err) { setError(err.message || 'The record could not be saved.'); }
    finally { setBusy(false); }
  };

  const markAllRead = async () => {
    try { setBusy(true); await request('/notifications/read-all', { method: 'POST' }); setNotice('All notifications marked read.'); await load(); }
    catch (err) { setError(err.message || 'Notifications could not be updated.'); }
    finally { setBusy(false); }
  };

  const updatePreference = async (eventType, field, value) => {
    const current = preferences.find((item) => item.event_type === eventType) || { event_type: eventType, in_app: true, email: false };
    const next = { ...current, [field]: value };
    setBusy(true); setError('');
    try { const saved = await request('/notifications/preferences', { method: 'PUT', body: JSON.stringify(next) }); setPreferences((items) => [...items.filter((item) => item.event_type !== eventType), saved]); }
    catch (err) { setError(err.message || 'Notification preference could not be saved.'); }
    finally { setBusy(false); }
  };

  const evaluateAssertion = async (assertionId) => {
    setBusy(true); setError(''); setNotice('');
    try {
      const result = await request(`/quality/assertions/${encodeURIComponent(assertionId)}/evaluate`, { method: 'POST' });
      setNotice(`Evaluation ${result.status || 'completed'}: ${result.checked_count ?? 0} metadata checks, ${result.failed_count ?? 0} failed.`);
      await load();
    } catch (err) { setError(err.message || 'Assertion evaluation failed.'); }
    finally { setBusy(false); }
  };

  const approveTerm = async (termId) => {
    setBusy(true); setError(''); setNotice('');
    try { await request(`/governance/terms/${encodeURIComponent(termId)}/approve`, { method: 'POST' }); setNotice('Glossary term approved.'); await load(); }
    catch (err) { setError(err.message || 'Term approval failed.'); }
    finally { setBusy(false); }
  };

  const assignTerm = async (event) => {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    setBusy(true); setError(''); setNotice('');
    try { await request(`/governance/terms/${encodeURIComponent(String(form.get('term_id') || '').trim())}/assets`, { method: 'POST', body: JSON.stringify({ dataset_id: String(form.get('dataset_id') || '').trim() }) }); event.currentTarget.reset(); setNotice('Glossary term linked to the catalog asset.'); await load(); }
    catch (err) { setError(err.message || 'Term assignment failed.'); }
    finally { setBusy(false); }
  };

  const createContract = async (event) => {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    setBusy(true); setError(''); setNotice('');
    try {
      let clauses;
      try { clauses = JSON.parse(String(form.get('clauses') || '[]')); } catch (_) { throw new Error('Clauses must be valid JSON.'); }
      if (!Array.isArray(clauses)) throw new Error('Clauses must be a JSON array.');
      const productId = String(form.get('product_id') || '').trim();
      await request(`/governance/products/${encodeURIComponent(productId)}/contracts`, { method: 'POST', body: JSON.stringify({ version: Number(form.get('version')), enforcement_mode: String(form.get('enforcement_mode')), clauses }) });
      event.currentTarget.reset(); setNotice('Data contract version saved.'); await load();
    } catch (err) { setError(err.message || 'Contract could not be saved.'); }
    finally { setBusy(false); }
  };

  const linkAssertion = async (event) => {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    setBusy(true); setError(''); setNotice('');
    try {
      await request(`/governance/contracts/${encodeURIComponent(String(form.get('contract_id') || '').trim())}/assertions`, { method: 'POST', body: JSON.stringify({ assertion_id: String(form.get('assertion_id') || '').trim(), clause_key: String(form.get('clause_key') || '').trim() }) });
      event.currentTarget.reset(); setNotice('Quality assertion linked to the contract clause.');
    } catch (err) { setError(err.message || 'Contract assertion link failed.'); }
    finally { setBusy(false); }
  };

  const sourceAction = async (sourceId, action) => {
    setBusy(true); setError(''); setNotice('');
    try {
      const result = action === 'revoke'
        ? await request(`/sources/${encodeURIComponent(sourceId)}`, { method: 'DELETE' })
        : await request(`/sources/${encodeURIComponent(sourceId)}/${action}`, { method: 'POST' });
      if (action === 'preview') setNotice(result.ok ? `Preview succeeded: ${result.preview?.assets ?? 0} assets and ${result.preview?.columns ?? 0} columns discovered. No catalog rows were written.` : result.commit_blocker || 'Source preview failed.');
      else if (action === 'sync') setNotice(`Source sync completed. Import ${result.import_id || 'status unavailable'}; persisted catalog readback is separate.`);
      else if (action === 'test') setNotice(result.ok ? 'Source schema test succeeded. This does not mean data has been imported.' : 'Source test failed. Check the source settings and grant only the requested read scope.');
      else setNotice('Source revoked. Historical catalog evidence is retained.');
      await load();
    } catch (err) { setError(err.message || 'Source action failed.'); }
    finally { setBusy(false); }
  };

  return <section className="kv-view kv-freshness-view" aria-labelledby="governanceViewTitle">
    <div className="kv-view-head"><div><h1 id="governanceViewTitle">{config.title}</h1><p className="kv-sub">Workspace data returned by the authenticated governance API.</p></div><div><DataModeLabel mode={demoPreview ? DATA_MODES.DEMO_FIXTURE : connected ? DATA_MODES.LIVE : DATA_MODES.NOT_CONNECTED} /><button className="btn" onClick={load} disabled={loading || busy || demoPreview} type="button">Refresh</button></div></div>
    {notice ? <p role="status" className="kv-note">{notice}</p> : null}
    {error ? <div role="alert" className="kv-note kv-note--error"><strong>Governance data unavailable</strong><p>{error}</p><p>No sample records are shown in place of an API failure.</p></div> : null}
    {view === 'notifications' && <section className="kv-card"><p>Realtime delivery is not connected to the authenticated workspace API yet. Refresh reads current persisted notifications.</p><button className="btn" onClick={markAllRead} disabled={busy || loading || !rows.some((row) => !row.read_at)} type="button">Mark all read</button></section>}
    {view === 'sources' && <section className="kv-card"><p>Source credentials are never displayed here. This M2 API currently supports PostgreSQL only. Scope discovery is limited to the selected schema; schedules, credential rotation, sync-history records, and credential-expiry checks are not available from the current API.</p></section>}
    {view === 'settings' && <section className="kv-card"><h2>Workspace access</h2><p>Member and role records are loaded from the M1 membership API. API key and webhook management endpoints are not present, so these controls are not shown as available.</p><h3>Notification preferences</h3><p>Email delivery is recorded as a preference only; no email delivery service is configured by this slice.</p>{preferencesError ? <p role="status">{preferencesError}</p> : NOTIFICATION_TYPES.map((type) => { const pref = preferences.find((item) => item.event_type === type) || { in_app: true, email: false }; return <div className="kv-preference-row" key={type}><strong>{type.replaceAll('_', ' ')}</strong><label><input type="checkbox" checked={Boolean(pref.in_app)} disabled={busy} onChange={(event) => updatePreference(type, 'in_app', event.target.checked)} /> In-app</label><label><input type="checkbox" checked={Boolean(pref.email)} disabled={busy} onChange={(event) => updatePreference(type, 'email', event.target.checked)} /> Email preference</label></div>; })}</section>}
    {['glossary', 'pii', 'domains', 'products', 'quality', 'sources', 'settings'].includes(view) && <form className="kv-card kv-freshness-form" onSubmit={submit}>
      <h2>{view === 'settings' ? 'Invite a workspace member' : view === 'glossary' ? 'Propose a glossary term' : view === 'pii' ? 'Record an evidence-backed classification' : view === 'domains' ? 'Create a domain' : view === 'products' ? 'Create a data product' : view === 'sources' ? 'Register a PostgreSQL source' : 'Create a quality assertion'}</h2>
      {view === 'settings' && <><label>Member email<input name="email" type="email" autoComplete="off" maxLength={320} required /></label><label>Workspace role<select name="role"><option value="viewer">Viewer</option><option value="editor">Editor</option><option value="admin">Admin</option></select></label><p>Invitation and role assignment are enforced by the authenticated M1 membership API. Owners cannot be granted through invitations.</p></>}
      {view !== 'pii' && <label>Name<input name="name" maxLength={160} required /></label>}
      {view === 'pii' && <><label>Dataset UUID<input name="dataset_id" required /></label><label>Column UUID (optional)<input name="column_id" /></label><label>Classification<select name="classification"><option>PII_SOURCE</option><option disabled title="Requires lineage evidence propagation, which is not configured yet.">PII_INHERITED (lineage evidence required)</option><option>PII_MASKED</option><option disabled title="Requires a persisted SQLGlot evidence reference.">PII_POTENTIAL (analysis evidence required)</option><option>PII_CLEARED</option><option>UNKNOWN</option></select></label><label>Evidence state<select name="evidence_state"><option>OBSERVED</option><option>POSSIBLE</option><option>UNKNOWN</option></select></label><label>Evidence/provenance note<input name="provenance_note" maxLength={1000} required /></label><p>Inherited and potential classes are disabled until their evidence pipeline is available. PII_CLEARED requires an active owner/admin reviewer. Classification metadata does not grant access to source data.</p></>}
      {view !== 'glossary' && view !== 'pii' && <label>Description<textarea name="description" maxLength={4000} /></label>}
      {view === 'glossary' && <label>Definition<textarea name="definition" maxLength={4000} required /></label>}
      {view === 'products' && <label>Catalog asset UUIDs (comma-separated)<input name="asset_ids" /></label>}
      {view === 'quality' && <><label>Dataset UUID<input name="dataset_id" required /></label><label>Assertion type<select name="assertion_type"><option value="freshness">Freshness</option><option value="completeness">Metadata completeness</option><option value="uniqueness">Canonical asset identity uniqueness</option><option value="validity">Schema metadata validity</option><option value="schema">Expected columns</option></select></label><label>Severity<select name="severity"><option>LOW</option><option>MEDIUM</option><option>HIGH</option><option>CRITICAL</option></select></label><p>Custom SQL is unavailable until a reviewed read-only source-query runner exists.</p></>}
      {view === 'sources' && <><label>Host<input name="host" autoComplete="off" maxLength={255} required /></label><label>Port<input name="port" type="number" min="1" max="65535" defaultValue="5432" required /></label><label>Database<input name="dbname" autoComplete="off" maxLength={128} required /></label><label>Username<input name="user" autoComplete="off" maxLength={128} required /></label><label>Password<input name="password" autoComplete="new-password" maxLength={512} required type="password" /></label><label>Schema<input name="schema_name" defaultValue="public" maxLength={128} required /></label><p>Credentials are sent only to the authenticated API, stored encrypted by the server, and never returned to this screen. Only PostgreSQL is currently supported; sync schedules and credential rotation are not implemented by the source API.</p></>}
      <p className="kv-freshness-placeholder">Saved records are workspace-scoped. Product health is shown only when source evaluation rows exist.</p>
      <button className="btn primary" disabled={busy} type="submit">{busy ? 'Saving…' : view === 'settings' ? 'Send invitation' : view === 'quality' ? 'Create assertion' : view === 'sources' ? 'Save encrypted source' : 'Save'}</button>
    </form>}
    {view === 'glossary' && <form className="kv-card kv-freshness-form" onSubmit={assignTerm}>
      <h2>Link a term to an asset</h2><label>Glossary term UUID<input name="term_id" required /></label><label>Dataset UUID<input name="dataset_id" required /></label><button className="btn" disabled={busy} type="submit">Link term</button>
    </form>}
    {view === 'products' && <>
      <form className="kv-card kv-freshness-form" onSubmit={createContract}>
        <h2>Create a versioned data contract</h2><label>Product UUID<input name="product_id" required /></label><label>Next version number<input name="version" type="number" min="1" required /></label><label>Enforcement mode<select name="enforcement_mode"><option>MONITOR</option><option>WARN</option><option>BLOCK</option></select></label><label>Clauses (JSON array)<textarea name="clauses" defaultValue="[]" maxLength={20000} required /></label><button className="btn" disabled={busy} type="submit">Save contract version</button>
      </form>
      <form className="kv-card kv-freshness-form" onSubmit={linkAssertion}>
        <h2>Bind a quality assertion to a contract clause</h2><label>Contract UUID<input name="contract_id" required /></label><label>Assertion UUID<input name="assertion_id" required /></label><label>Clause key<input name="clause_key" maxLength={120} required /></label><button className="btn" disabled={busy} type="submit">Link assertion</button>
      </form>
    </>}
    <section className="kv-card"><h2>{view === 'notifications' ? 'Notification history' : `${config.title} records`}</h2>
      {loading ? <p role="status">Loading {config.title.toLowerCase()}…</p> : rows.length === 0 ? <p className="kv-freshness-placeholder">No {config.title.toLowerCase()} records were returned.</p> : <div className="kv-table-wrap"><table className="kv-table"><thead><tr>{view === 'notifications' ? <><th>Event</th><th>Title</th><th>Created</th><th>State</th><th>Action</th></> : view === 'quality' ? <><th>Assertion</th><th>Asset</th><th>Type</th><th>Latest result</th><th>Failures</th><th>Action</th></> : view === 'sources' ? <><th>Name</th><th>Type</th><th>Status</th><th>Last checked</th><th>Actions</th></> : view === 'settings' ? <><th>User ID</th><th>Role</th><th>Status</th><th>Joined</th></> : <><th>Name</th><th>Description / definition</th><th>Status</th><th>Updated</th>{view === 'products' && <th>Contract</th>}{view === 'glossary' && <th>Action</th>}</>}</tr></thead><tbody>{rows.map((row, index) => <tr key={row.id || index}>{view === 'notifications' ? <><td>{row.event_type}</td><td>{row.title}</td><td>{row.created_at || '—'}</td><td>{row.read_at ? 'Read' : 'Unread'}</td><td>{row.action_path && row.action_path.startsWith('/') && !row.action_path.startsWith('//') && <a href={row.action_path}>Open related record</a>} {!row.read_at && <button className="btn small" disabled={busy} onClick={() => { request('/notifications/read', { method: 'POST', body: JSON.stringify({ notification_ids: [row.id] }) }).then(load).catch((err) => setError(err.message)); }} type="button">Mark read</button>}</td></> : view === 'quality' ? <><td>{row.name}</td><td>{row.dataset_name || row.dataset_id}</td><td>{row.assertion_type}</td><td>{row.latest_status || 'Not evaluated'}</td><td>{row.failed_count ?? '—'}</td><td><button className="btn small" disabled={busy} onClick={() => evaluateAssertion(row.id)} type="button">Evaluate</button></td></> : view === 'sources' ? <><td>{row.name}</td><td>{row.source_kind}</td><td>{row.lifecycle_state}</td><td>{row.last_checked_at || 'Not checked'}</td><td><button className="btn small" disabled={busy} onClick={() => sourceAction(row.id, 'test')} type="button">Test</button> <button className="btn small" disabled={busy} onClick={() => sourceAction(row.id, 'preview')} type="button">Preview</button> <button className="btn small" disabled={busy || row.lifecycle_state === 'REVOKED'} onClick={() => sourceAction(row.id, 'sync')} type="button">Sync now</button> <button className="btn small" disabled={busy || row.lifecycle_state === 'REVOKED'} onClick={() => sourceAction(row.id, 'revoke')} type="button">Revoke</button></td></> : view === 'settings' ? <><td>{row.user_id}</td><td>{row.role}</td><td>{row.status}</td><td>{row.created_at || '—'}</td></> : <><td>{row.name}</td><td>{row.definition || row.description || 'Not recorded'}</td><td>{row.status || 'Not recorded'}</td><td>{row.updated_at || row.created_at || '—'}</td>{view === 'products' && <td>{row.contract_version ? `v${row.contract_version} · ${row.contract_enforcement_mode}` : 'No contract version'}</td>}{view === 'glossary' && <td>{row.status === 'DRAFT' && <button className="btn small" disabled={busy} onClick={() => approveTerm(row.id)} type="button">Approve</button>}</td>}</>}</tr>)}</tbody></table></div>}
    </section>
  </section>;
}
