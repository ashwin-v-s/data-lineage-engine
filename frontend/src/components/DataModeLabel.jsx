import React from 'react';

import {
  dataModeDescription,
  dataModeToken,
  normalizeDataMode,
} from './dataMode.js';

/**
 * The single badge that states where the data on screen came from.
 *
 * It never guesses upwards: an unknown or missing mode is rendered as the
 * demonstration-fixture mode rather than as live connected data.
 */
export default function DataModeLabel({ mode, className = '' }) {
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
