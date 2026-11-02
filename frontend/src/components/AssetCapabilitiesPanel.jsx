import React, { useEffect, useState } from 'react';

import {
  availableTabs,
  capabilityDescription,
  capabilityLabel,
  fetchCapabilities,
} from '../views/capabilities.js';

import './AssetCapabilitiesPanel.css';

/**
 * A capability-driven tab strip for one asset.
 *
 * The tabs are derived entirely from the backend capability registry: only the
 * capabilities the registry reports as available become tabs. Capabilities the
 * registry cannot provide are never hidden silently — they are listed below
 * with the reason Kairos gives. No rows, numbers or sample values are ever
 * fabricated; a selected tab states what the capability means and that its data
 * is served live.
 */
export default function AssetCapabilitiesPanel({ assetId }) {
  const [state, setState] = useState({ status: 'loading', registry: null, error: null });
  const [selectedKey, setSelectedKey] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setState({ status: 'loading', registry: null, error: null });
    setSelectedKey(null);
    fetchCapabilities(assetId).then((result) => {
      if (cancelled) return;
      if (result.ok) {
        const tabs = availableTabs(result.registry);
        setState({ status: 'ready', registry: result.registry, error: null });
        setSelectedKey(tabs.length ? tabs[0].key : null);
      } else {
        setState({ status: 'error', registry: null, error: result.error });
      }
    });
    return () => { cancelled = true; };
  }, [assetId]);

  if (state.status === 'loading') {
    return (
      <div className="kv-caps">
        <p className="kv-note">Loading asset capabilities…</p>
      </div>
    );
  }

  if (state.status === 'error') {
    return (
      <div className="kv-caps">
        <p className="kv-note kv-note--error">
          {state.error} No capability data is substituted while the live API is unreachable.
        </p>
      </div>
    );
  }

  const { registry } = state;
  const tabs = availableTabs(registry);
  const unavailable = registry.capabilities.filter((entry) => !entry.available);
  const selectedEntry = tabs.find((entry) => entry.key === selectedKey) || null;

  return (
    <div className="kv-caps">
      {tabs.length === 0 ? (
        <p className="kv-empty">
          This asset currently publishes no available capability. Every capability Kairos cannot
          provide is listed below with the reason.
        </p>
      ) : (
        <>
          <div className="kv-caps-tablist" role="tablist" aria-label="Asset capabilities">
            {tabs.map((entry) => (
              <button
                key={entry.key}
                type="button"
                role="tab"
                className="kv-caps-tab"
                data-capability={entry.key}
                aria-selected={entry.key === selectedKey}
                onClick={() => setSelectedKey(entry.key)}
              >
                {capabilityLabel(entry.key)}
              </button>
            ))}
          </div>
          {selectedEntry && (
            <div
              className="kv-caps-panel"
              role="tabpanel"
              data-capability-panel={selectedEntry.key}
              aria-label={capabilityLabel(selectedEntry.key)}
            >
              <strong className="kv-caps-panel-title">{capabilityLabel(selectedEntry.key)}</strong>
              <p className="kv-hint">{capabilityDescription(selectedEntry.key)}</p>
              <p className="kv-hint">
                This tab is populated live by Kairos from the asset's stored evidence; no rows or
                values are synthesised here.
              </p>
            </div>
          )}
        </>
      )}

      {unavailable.length > 0 && (
        <div className="kv-caps-unavailable-block">
          <p className="kv-hint">Capabilities Kairos cannot show for this asset, and why:</p>
          <ul className="kv-caps-unavailable kv-muted">
            {unavailable.map((entry) => (
              <li key={entry.key}>
                <span className="kv-caps-entry-key">{capabilityLabel(entry.key)}</span>
                {' — '}
                {entry.reason}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
