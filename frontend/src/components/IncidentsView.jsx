import React, { useCallback, useEffect, useRef, useState } from 'react';

import DataModeLabel from './DataModeLabel.jsx';
import { DATA_MODES } from './dataMode.js';
import {
  INCIDENT_STATUSES,
  allowedIncidentActions,
  applyIncidentAction,
  fetchIncident,
  fetchIncidents,
  formatTimestamp,
  incidentSeverityChipToken,
  incidentStatusChipToken,
  severityExplanation,
  statusExplanation,
  summarizeTransition,
} from '../views/incidents.js';
import { API_BASE, requestJson } from '../api/client.js';
import './IncidentsView.css';

/** The status filter offers `All` plus every canonical status. */
const FILTERS = ['ALL', ...INCIDENT_STATUSES];

const ACTION_LABELS = {
  acknowledge: 'Acknowledge',
  investigate: 'Investigate',
  resolve: 'Resolve',
};

/**
 * Render a value as a bounded, plain-text JSON block. Long values are truncated
 * so the timeline stays readable; nothing is ever injected as HTML.
 * @param {unknown} value
 * @param {number} [limit]
 * @returns {string}
 */
function jsonPreview(value, limit = 480) {
  if (value === null || value === undefined) return '—';
  let text;
  try {
    text = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  } catch (_error) {
    text = String(value);
  }
  if (text === undefined) text = String(value);
  return text.length > limit ? `${text.slice(0, limit)}…` : text;
}

/** The incidents stored on the server, rendered from live responses only. */
export default function IncidentsView({ demoPreview = false } = {}) {
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [incidents, setIncidents] = useState([]);
  const [count, setCount] = useState(0);
  const [listError, setListError] = useState(null);
  const [listLoading, setListLoading] = useState(true);
  const [live, setLive] = useState(false);

  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailError, setDetailError] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [busyAction, setBusyAction] = useState(null);
  const [notice, setNotice] = useState(null);
  const [noticeError, setNoticeError] = useState(null);
  const [resolutionReason, setResolutionReason] = useState('');
  const [resolutionAction, setResolutionAction] = useState('');
  const [comment, setComment] = useState('');
  const [assignmentUserId, setAssignmentUserId] = useState('');

  const [reloadKey, setReloadKey] = useState(0);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  // Load the list whenever the filter (or an explicit reload) changes.
  useEffect(() => {
    let cancelled = false;
    setListLoading(true);
    if (demoPreview) {
      setIncidents([]);
      setCount(0);
      setListError('Incidents are unavailable in demo preview. No sample incidents are substituted.');
      setListLoading(false);
      return () => { cancelled = true; };
    }
    fetchIncidents({ status: statusFilter }).then((result) => {
      if (cancelled || !mountedRef.current) return;
      if (result.ok) {
        setIncidents(result.incidents);
        setCount(result.count);
        setLive(true);
        setListError(null);
      } else {
        setIncidents([]);
        setCount(0);
        setListError(result.error);
      }
      setListLoading(false);
    });
    return () => { cancelled = true; };
  }, [demoPreview, statusFilter, reloadKey]);

  const handleSelect = useCallback((id) => {
    if (!id) return;
    setSelectedId(id);
    setDetail(null);
    setDetailError(null);
    setNotice(null);
    setNoticeError(null);
    setDetailLoading(true);
    fetchIncident(id).then((result) => {
      if (!mountedRef.current) return;
      setDetailLoading(false);
      if (result.ok) setDetail(result.incident);
      else setDetailError(result.error);
    });
  }, []);

  const handleAction = useCallback((action) => {
    if (!detail || !detail.id) return;
    const previousStatus = detail.status;
    setNotice(null);
    setNoticeError(null);
    const body = action === 'resolve' ? { reason: resolutionReason.trim(), action_taken: resolutionAction.trim() } : undefined;
    if (action === 'resolve' && (!body.reason || !body.action_taken)) {
      setBusyAction(null);
      setNoticeError('Record a resolution reason and action before closing this incident.');
      return;
    }
    setBusyAction(action);
    applyIncidentAction(detail.id, action, { body }).then((result) => {
      if (!mountedRef.current) return;
      setBusyAction(null);
      if (result.ok) {
        setDetail(result.incident);
        setSelectedId(result.incident.id);
        setNotice(summarizeTransition(previousStatus, action));
        setReloadKey((key) => key + 1);
      } else {
        setNoticeError(result.error);
      }
    });
  }, [detail, resolutionReason, resolutionAction]);

  const handleComment = async (event) => {
    event.preventDefault();
    if (!detail?.id || !comment.trim()) return;
    setBusyAction('comment'); setNoticeError(null); setNotice(null);
    try {
      await requestJson(`${API_BASE}/governance/incidents/${encodeURIComponent(detail.id)}/comments`, { method: 'POST', body: { comment: comment.trim() } });
      setComment(''); setNotice('Comment added to the incident timeline.'); handleSelect(detail.id);
    } catch (error) { setNoticeError(error.message || 'Comment could not be added.'); }
    finally { setBusyAction(null); }
  };

  const handleAssign = async (event) => {
    event.preventDefault();
    if (!detail?.id || !assignmentUserId.trim()) return;
    setBusyAction('assign'); setNoticeError(null); setNotice(null);
    try {
      await requestJson(`${API_BASE}/governance/incidents/${encodeURIComponent(detail.id)}/assign`, { method: 'POST', body: { user_id: assignmentUserId.trim() } });
      setAssignmentUserId(''); setNotice('Incident assigned to the workspace member.'); handleSelect(detail.id); setReloadKey((key) => key + 1);
    } catch (error) { setNoticeError(error.message || 'Incident could not be assigned.'); }
    finally { setBusyAction(null); }
  };

  const allowed = detail ? allowedIncidentActions(detail.status) : [];

  return (
    <section className="kv-view" data-live-view="incidents">
      <div className="kv-view-head">
        <h1>Incident console</h1>
        {live ? <DataModeLabel mode={DATA_MODES.LIVE} /> : demoPreview ? <DataModeLabel mode={DATA_MODES.DEMO_FIXTURE} /> : null}
      </div>
      <p className="kv-sub">
        {demoPreview ? 'Incident records are not included in the demo preview.' : null}
        {!demoPreview ? <>
        This console reads the live incidents written by the Kairos freshness engine.
        Severity follows the breach that opened the incident: a STALE verdict opens a
        HIGH incident and a LATE verdict opens a MEDIUM one; every other breach is LOW.
        </> : null}
      </p>

      <div className="kv-toolbar">
        {FILTERS.map((filter) => (
          <button
            key={filter}
            aria-pressed={statusFilter === filter}
            className={`kv-btn kv-incidents-filter${statusFilter === filter ? ' kv-incidents-filter--active' : ''}`}
            onClick={() => setStatusFilter(filter)}
            type="button"
          >
            {filter === 'ALL' ? 'All' : filter}
          </button>
        ))}
        <span className="kv-spacer" />
        <span className="kv-muted kv-incidents-count">
          {count} {count === 1 ? 'incident' : 'incidents'}
        </span>
      </div>

      {listError ? (
        <p className="kv-note kv-note--error">
          {listError}{demoPreview ? '' : ' No sample incidents are substituted while the live API is unreachable.'}
        </p>
      ) : null}

      {!listError && !listLoading && incidents.length === 0 ? (
        <p className="kv-empty">
          No incident is currently recorded — either no SLA breach has been detected yet,
          or every incident has been resolved.
        </p>
      ) : null}

      {incidents.length > 0 ? (
        <div className="kv-table-wrap">
          <table className="kv-table kv-incidents-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Dataset</th>
                <th>Severity</th>
                <th>Status</th>
                <th>Opened</th>
                <th>Acknowledged</th>
                <th>Resolved</th>
              </tr>
            </thead>
            <tbody>
              {incidents.map((incident) => (
                <tr
                  key={incident.id}
                  aria-selected={selectedId === incident.id}
                  className={`kv-incidents-row${selectedId === incident.id ? ' kv-incidents-row--selected' : ''}`}
                  onClick={() => handleSelect(incident.id)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      handleSelect(incident.id);
                    }
                  }}
                  tabIndex={0}
                >
                  <td>{incident.title || <span className="kv-muted">Untitled incident</span>}</td>
                  <td>
                    <div>{incident.datasetName || <span className="kv-muted">Unknown dataset</span>}</div>
                    <div className="kv-mono kv-muted">{incident.datasetId || '—'}</div>
                  </td>
                  <td>
                    <span className={`kv-chip kv-chip--${incidentSeverityChipToken(incident.severity)}`}>
                      {incident.severity}
                    </span>
                  </td>
                  <td>
                    <span className={`kv-chip kv-chip--${incidentStatusChipToken(incident.status)}`}>
                      {incident.status}
                    </span>
                  </td>
                  <td className="kv-mono">{formatTimestamp(incident.openedAt) || '—'}</td>
                  <td className="kv-mono">{formatTimestamp(incident.acknowledgedAt) || '—'}</td>
                  <td className="kv-mono">{formatTimestamp(incident.resolvedAt) || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {detailError ? <p className="kv-note kv-note--error">{detailError}</p> : null}

      <div className="kv-card kv-incidents-detail">
        <h2>Incident detail</h2>

        {!selectedId ? (
          <p className="kv-muted kv-incidents-placeholder">
            Select an incident to see its fields and event timeline.
          </p>
        ) : null}

        {selectedId && detailLoading && !detail ? (
          <p className="kv-muted kv-incidents-placeholder">Loading incident…</p>
        ) : null}

        {detail ? (
          <>
            <dl className="kv-incidents-fields">
              <div>
                <dt>Title</dt>
                <dd>{detail.title || '—'}</dd>
              </div>
              <div>
                <dt>Dataset</dt>
                <dd>
                  {detail.datasetName || 'Unknown dataset'}{' '}
                  <span className="kv-mono kv-muted">{detail.datasetId || '—'}</span>
                </dd>
              </div>
              <div>
                <dt>Severity</dt>
                <dd>
                  <span className={`kv-chip kv-chip--${incidentSeverityChipToken(detail.severity)}`}>
                    {detail.severity}
                  </span>{' '}
                  <span className="kv-hint">{severityExplanation(detail.severity)}</span>
                </dd>
              </div>
              <div>
                <dt>Status</dt>
                <dd>
                  <span className={`kv-chip kv-chip--${incidentStatusChipToken(detail.status)}`}>
                    {detail.status}
                  </span>{' '}
                  <span className="kv-hint">{statusExplanation(detail.status)}</span>
                </dd>
              </div>
              <div>
                <dt>Opened</dt>
                <dd className="kv-mono">{formatTimestamp(detail.openedAt) || '—'}</dd>
              </div>
              <div>
                <dt>Acknowledged</dt>
                <dd className="kv-mono">{formatTimestamp(detail.acknowledgedAt) || '—'}</dd>
              </div>
              <div>
                <dt>Resolved</dt>
                <dd className="kv-mono">{formatTimestamp(detail.resolvedAt) || '—'}</dd>
              </div>
              <div>
                <dt>Owner</dt>
                <dd className="kv-mono">{detail.ownerUserId || 'Unassigned'}</dd>
              </div>
              <div>
                <dt>Dedupe key</dt>
                <dd className="kv-mono">{detail.dedupeKey || '—'}</dd>
              </div>
              <div className="kv-incidents-fields-wide">
                <dt>Detail</dt>
                <dd>
                  <pre className="kv-mono kv-incidents-json">{jsonPreview(detail.detail)}</pre>
                </dd>
              </div>
              {detail.resolutionDetail && Object.keys(detail.resolutionDetail).length > 0 && <div className="kv-incidents-fields-wide">
                <dt>Resolution evidence</dt>
                <dd><pre className="kv-mono kv-incidents-json">{jsonPreview(detail.resolutionDetail)}</pre></dd>
              </div>}
            </dl>

            <div className="kv-actions kv-incidents-actions">
              {allowed.length > 0 ? (
                allowed.map((action) => (
                  <button
                    key={action}
                    className={`kv-btn${action === 'acknowledge' ? ' kv-btn--primary' : ''}${action === 'resolve' ? ' kv-btn--danger' : ''}`}
                    disabled={busyAction !== null}
                    onClick={() => handleAction(action)}
                    type="button"
                  >
                    {busyAction === action ? `${ACTION_LABELS[action]}…` : ACTION_LABELS[action]}
                  </button>
                ))
              ) : (
                <span className="kv-muted kv-incidents-placeholder">
                  No action is available: the incident is resolved.
                </span>
              )}
            </div>

            {detail.status !== 'RESOLVED' && <>
              <form className="kv-card" onSubmit={handleAssign}>
                <label>Assign to active workspace member (user UUID)<input value={assignmentUserId} onChange={(event) => setAssignmentUserId(event.target.value)} maxLength={36} required /></label>
                <button className="kv-btn" disabled={busyAction !== null || !assignmentUserId.trim()} type="submit">Assign incident</button>
              </form>
              {allowed.includes('resolve') && <div className="kv-card">
                <label>Resolution reason<textarea value={resolutionReason} onChange={(event) => setResolutionReason(event.target.value)} maxLength={2000} required /></label>
                <label>Action taken<textarea value={resolutionAction} onChange={(event) => setResolutionAction(event.target.value)} maxLength={2000} required /></label>
                <p className="kv-muted">The API stores the reason, action, actor, and resolution time with the incident.</p>
              </div>}
              <form className="kv-card" onSubmit={handleComment}>
                <label>Add incident comment<textarea value={comment} onChange={(event) => setComment(event.target.value)} maxLength={4000} required /></label>
                <button className="kv-btn" disabled={busyAction !== null || !comment.trim()} type="submit">Add comment</button>
              </form>
            </>}

            {notice ? <p className="kv-note kv-note--ok">{notice}</p> : null}
            {noticeError ? <p className="kv-note kv-note--error">{noticeError}</p> : null}

            <div className="kv-incidents-timeline">
              <h3 className="kv-incidents-timeline-title">Event timeline</h3>
              {detail.events.length === 0 ? (
                <p className="kv-muted kv-incidents-placeholder">
                  No events have been recorded for this incident yet.
                </p>
              ) : (
                <ol className="kv-incidents-events">
                  {detail.events.map((event, index) => (
                    <li key={event.id || `${event.eventType || 'event'}-${index}`} className="kv-incidents-event">
                      <div className="kv-incidents-event-head">
                        <span className="kv-chip kv-chip--info">{event.eventType || 'EVENT'}</span>
                        <span className="kv-mono kv-muted">{event.actorUserId || 'system'}</span>
                        <span className="kv-mono kv-muted kv-incidents-event-time">
                          {formatTimestamp(event.createdAt) || '—'}
                        </span>
                      </div>
                      <pre className="kv-mono kv-incidents-json">{jsonPreview(event.detail)}</pre>
                    </li>
                  ))}
                </ol>
              )}
            </div>
            <section className="kv-card" aria-label="Related incident history">
              <h3>Related incidents for this asset</h3>
              {detail.relatedIncidents?.length
                ? <ul>{detail.relatedIncidents.map((incident) => <li key={incident.id}>{incident.title} · {incident.status} · {formatTimestamp(incident.opened_at) || 'time unavailable'}</li>)}</ul>
                : <p className="kv-muted">No other stored incidents for this asset.</p>}
            </section>
          </>
        ) : null}
      </div>
    </section>
  );
}
