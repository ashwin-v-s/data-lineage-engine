(function (root) {
  'use strict';

  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char]);

  function report(message, isError = false) {
    if (typeof document === 'undefined') return;
    const region = document.getElementById('toastRegion');
    if (!region) return;
    const toast = document.createElement('div');
    toast.className = `toast${isError ? ' error' : ''}`;
    toast.textContent = message;
    region.append(toast);
    if (typeof window !== 'undefined' && typeof window.setTimeout === 'function') {
      window.setTimeout(() => toast.remove(), 4500);
    }
  }

  function openRemovalDialog(target) {
    if (typeof document === 'undefined') return;
    const backdrop = document.getElementById('modalBackdrop');
    const title = document.getElementById('modalTitle');
    const body = document.getElementById('modalBody');
    if (!backdrop || !title || !body) return;

    let id = '';
    let name = 'this asset';

    if (target && typeof target === 'object') {
      if (target.dataset) {
        id = target.dataset.id || '';
        name = target.dataset.name || 'this asset';
      } else {
        id = target.id || '';
        name = target.name || 'this asset';
      }
    }

    title.textContent = 'Remove asset from active catalog?';
    body.innerHTML = `
      <form id="assetRemovalForm" data-asset-id="${escapeHtml(id)}">
        <p>Remove <strong>${escapeHtml(name)}</strong> from the active catalog?</p>
        <p class="small-note">This hides the asset from normal catalog views. Lineage, evidence, raw events, and audit history are retained. Importing the same asset again restores it.</p>
        <p class="small-note">Only workspace owners and admins can remove assets.</p>
        <div class="toolbar">
          <button class="btn" type="button" data-action="close-modal">Cancel</button>
          <button class="btn danger" type="submit">Remove from catalog</button>
        </div>
        <p id="assetRemovalMessage" role="alert" aria-live="polite"></p>
      </form>`;
    backdrop.hidden = false;
    document.getElementById('modalClose')?.focus();
  }

  function closeRemovalDialog() {
    if (typeof document === 'undefined') return;
    const backdrop = document.getElementById('modalBackdrop');
    if (backdrop) backdrop.hidden = true;
  }

  async function submitRemoval(assetId, options = {}) {
    const { submit, message } = options;
    if (submit) {
      submit.disabled = true;
      submit.textContent = 'Removing...';
    }
    try {
      const response = await fetch(`/api/v1/assets/${encodeURIComponent(assetId)}`, {
        method: 'DELETE',
        credentials: 'same-origin',
        headers: { Accept: 'application/json' },
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || !result.ok) {
        const detail = result.detail;
        throw new Error(typeof detail === 'string' ? detail : detail?.message || `Removal failed (HTTP ${response.status}).`);
      }
      closeRemovalDialog();
      report('Asset removed from the active catalog. Its lineage and evidence history remain available.');
      if (typeof document !== 'undefined') {
        document.dispatchEvent(new CustomEvent('kairos:asset-removed', {
          detail: { assetId },
        }));
      }
      return result;
    } catch (error) {
      if (message) message.textContent = error.message || 'Asset removal failed.';
      if (submit) {
        submit.disabled = false;
        submit.textContent = 'Remove from catalog';
      }
      throw error;
    }
  }

  if (typeof document !== 'undefined') {
    document.addEventListener('click', (event) => {
      const button = event.target.closest('[data-action="remove-asset"]');
      if (button) {
        event.preventDefault();
        event.stopPropagation();
        openRemovalDialog(button);
        return;
      }
      const closeBtn = event.target.closest('#assetRemovalForm [data-action="close-modal"]');
      if (closeBtn) {
        event.preventDefault();
        event.stopPropagation();
        closeRemovalDialog();
      }
    });

    document.addEventListener('submit', async (event) => {
      const form = event.target;
      if (form?.id !== 'assetRemovalForm') return;
      event.preventDefault();
      const submit = form.querySelector('[type="submit"]');
      const message = document.getElementById('assetRemovalMessage');
      const assetId = form.dataset.assetId || '';
      try {
        await submitRemoval(assetId, { submit, message });
      } catch (_) {
        // Error message rendered to #assetRemovalMessage
      }
    });
  }

  const api = Object.freeze({
    escapeHtml,
    report,
    openRemovalDialog,
    closeRemovalDialog,
    submitRemoval,
  });
  root.KairosAssetRemoval = api;
  if (typeof globalThis !== 'undefined') {
    globalThis.KairosAssetRemoval = api;
  }
})(typeof window !== 'undefined' ? window : globalThis);
