import React from 'react';

import {
  CONNECTING_DESCRIPTION,
  dataModeDescription,
  dataModeToken,
  normalizeDataMode,
} from './dataMode.js';

/**
 * The single badge that states where the data on screen came from.
 *
 * The connected label is shown only after this page session receives a
 * successful authenticated catalog response. While that request is still in
 * flight the badge says CONNECTING and loops a spinner: it must not claim the
 * workspace is disconnected before the catalog answers.
 */
export default function DataModeLabel({ mode, connecting = false, className = '' }) {
  if (connecting) {
    return (
      <span
        aria-live="polite"
        className={`data-mode-badge data-mode-badge--connecting${className ? ` ${className}` : ''}`}
        data-mode="connecting"
        role="status"
        title={CONNECTING_DESCRIPTION}
      >
        <span aria-hidden="true" className="data-mode-spinner" />
        CONNECTING
      </span>
    );
  }
  const resolved = normalizeDataMode(mode);
  const token = dataModeToken(resolved);
  return (
    <span
      className={`data-mode-badge data-mode-badge--${token}${className ? ` ${className}` : ''}`}
      data-mode={token}
      title={dataModeDescription(resolved)}
    >
      {resolved}
    </span>
  );
}
