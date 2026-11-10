(() => {
  'use strict';

  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char]);

  function report(message, isError = false) {
    const region = document.getElementById('toastRegion');
    if (!region) return;
    const toast = document.createElement('div');
    toast.className = `toast${isError ? ' error' : ''}`;
    toast.textContent = message;
    region.append(toast);
    window.setTimeout(() => toast.remove(), 4500);
  }

  function openRemovalDialog(button) {
    const backdrop = document.getElementById('modalBackdrop');
    const title = document.getElementById('modalTitle');
    const body = document.getElementById('modalBody');
    if (!backdrop || !title || !body) return;
    const id = button.dataset.id || '';
    const name = button.dataset.name || 'this asset';
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

  document.addEventListener('click', (event) => {
    const button = event.target.closest('[data-action="remove-asset"]');
    if (!button) return;
    event.preventDefault();
    event.stopPropagation();
    openRemovalDialog(button);
  });

  document.addEventListener('submit', async (event) => {
    const form = event.target;
    if (form?.id !== 'assetRemovalForm') return;
    event.preventDefault();
    const submit = form.querySelector('[type="submit"]');
    const message = document.getElementById('assetRemovalMessage');
    submit.disabled = true;
    try {
      const response = await fetch(`/api/v1/assets/${encodeURIComponent(form.dataset.assetId)}`, {
        method: 'DELETE',
        credentials: 'same-origin',
        headers: { Accept: 'application/json' },
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || !result.ok) {
        const detail = result.detail;
        throw new Error(typeof detail === 'string' ? detail : detail?.message || `Removal failed (HTTP ${response.status}).`);
      }
      document.getElementById('modalBackdrop').hidden = true;
      report('Asset removed from the active catalog. Its lineage and evidence history remain available.');
      window.location.reload();
    } catch (error) {
      if (message) message.textContent = error.message || 'Asset removal failed.';
      submit.disabled = false;
    }
  });
})();
