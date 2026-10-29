(() => {
  'use strict';
  const q = (selector, root = document) => root.querySelector(selector);
  const make = (tag, attrs = {}, text = '') => {
    const el = document.createElement(tag);
    Object.entries(attrs).forEach(([key, value]) => el.setAttribute(key, value));
    if (text) el.textContent = text;
    return el;
  };
  async function getCatalog() {
    const response = await fetch('/api/v1/catalog', { credentials: 'same-origin', headers: { Accept: 'application/json' } });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.message || data.error || 'Catalog request failed.');
    return data;
  }
  function syncDialogFields(dialog) {
    const entity = q('#kairosClassEntity', dialog).value;
    q('#kairosClassColumnWrap', dialog).hidden = entity !== 'column';
    const asset = dialog.__kairosAsset || {};
    const columnName = q('#kairosClassColumn', dialog).value;
    const record = entity === 'asset' ? asset : (dialog.__kairosColumnClassifications || {})[columnName];
    q('#kairosClassPii', dialog).value = record && record.is_pii === true ? 'true' : record && record.is_pii === false ? 'false' : 'null';
    q('#kairosClassSensitivity', dialog).value = record && record.sensitivity_classification || '';
  }
  function ensureDialog() {
    let dialog = q('#kairosClassificationDialog');
    if (dialog) return dialog;
    dialog = make('dialog', { id: 'kairosClassificationDialog', 'aria-labelledby': 'kairosClassificationTitle' });
    dialog.style.cssText = 'max-width:560px;width:calc(100% - 32px);border:1px solid #334155;border-radius:14px;padding:24px;background:#0B1220;color:#e5edf7;box-shadow:0 24px 80px #0009';
    dialog.innerHTML = '<form id="kairosClassificationForm"><h2 id="kairosClassificationTitle">PII &amp; sensitivity classification</h2><p class="small-note">Persist a reviewed classification in PostgreSQL. “Not classified” is not the same as “not PII”.</p><input type="hidden" id="kairosClassAsset"><label class="field"><span>Apply to</span><select id="kairosClassEntity"><option value="asset">Whole asset</option><option value="column">Specific column</option></select></label><label class="field" id="kairosClassColumnWrap" hidden><span>Column</span><select id="kairosClassColumn"></select></label><label class="field"><span>PII review</span><select id="kairosClassPii"><option value="null">Not classified / clear decision</option><option value="true">Confirmed PII</option><option value="false">Reviewed — not PII</option></select></label><label class="field"><span>Sensitivity classification</span><select id="kairosClassSensitivity"><option value="">No classification</option><option>PII</option><option>PHI</option><option>CONFIDENTIAL</option><option>INTERNAL</option><option>PUBLIC</option></select></label><div style="display:flex;gap:8px;justify-content:flex-end;margin-top:18px"><button type="button" class="btn" id="kairosClassCancel">Cancel</button><button type="submit" class="btn primary">Save classification</button></div><p id="kairosClassMessage" role="status" aria-live="polite"></p></form>';
    document.body.append(dialog);
    q('#kairosClassCancel', dialog).addEventListener('click', () => dialog.close());
    q('#kairosClassEntity', dialog).addEventListener('change', () => syncDialogFields(dialog));
    q('#kairosClassColumn', dialog).addEventListener('change', () => syncDialogFields(dialog));
    q('#kairosClassificationForm', dialog).addEventListener('submit', async event => {
      event.preventDefault();
      const form = event.currentTarget, submit = q('button[type="submit"]', form), entity_type = q('#kairosClassEntity', form).value;
      const raw = q('#kairosClassPii', form).value;
      const body = { entity_type, asset_id: q('#kairosClassAsset', form).value, is_pii: raw === 'null' ? null : raw === 'true', sensitivity_classification: q('#kairosClassSensitivity', form).value || null, classification_source: 'manual_review' };
      if (entity_type === 'column') body.column_name = q('#kairosClassColumn', form).value;
      submit.disabled = true;
      q('#kairosClassMessage', form).textContent = 'Saving…';
      try {
        const response = await fetch('/api/v1/pii-classification', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify(body) });
        const result = await response.json();
        if (!response.ok || !result.ok) throw new Error(result.message || result.error || 'Classification could not be saved.');
        q('#kairosClassMessage', form).textContent = 'Saved. Reloading persisted metadata…';
        window.location.reload();
      } catch (error) {
        q('#kairosClassMessage', form).textContent = error.message || 'Classification could not be saved.';
      } finally { submit.disabled = false; }
    });
    return dialog;
  }
  async function openClassification(assetId) {
    try {
      const data = await getCatalog();
      const asset = (data.assets || []).find(row => String(row.id) === String(assetId));
      if (!asset) throw new Error('Asset not found in the persisted catalog.');
      const classResponse = await fetch('/api/v1/pii-classification?asset_id=' + encodeURIComponent(assetId), { credentials: 'same-origin', headers: { Accept: 'application/json' } });
      const classData = await classResponse.json();
      if (!classResponse.ok || !classData.ok) throw new Error(classData.message || classData.error || 'Could not load persisted column classifications.');
      const columns = asset.metadata && asset.metadata.columns && typeof asset.metadata.columns === 'object' ? Object.keys(asset.metadata.columns) : [];
      const dialog = ensureDialog();
      dialog.__kairosAsset = asset;
      dialog.__kairosColumnClassifications = Object.fromEntries((classData.classifications || []).map(row => [row.column_name, row]));
      q('#kairosClassAsset', dialog).value = asset.id;
      const entity = q('#kairosClassEntity', dialog);
      entity.value = 'asset';
      const columnSelect = q('#kairosClassColumn', dialog);
      columnSelect.replaceChildren(...columns.map(name => make('option', { value: name }, name)));
      const columnOption = [...entity.options].find(option => option.value === 'column');
      if (columnOption) columnOption.disabled = columns.length === 0;
      syncDialogFields(dialog);
      q('#kairosClassMessage', dialog).textContent = '';
      dialog.showModal();
    } catch (error) { window.alert(error.message || 'Could not open classification editor.'); }
  }
  async function exportSnapshot() {
    try {
      const valid = q('#validTime')?.value, recorded = q('#recordedTime')?.value;
      const params = new URLSearchParams();
      if (valid) params.set('valid_as_of', new Date(valid).toISOString());
      if (recorded) params.set('recorded_as_of', new Date(recorded).toISOString());
      const response = await fetch('/api/v1/lineage/export?' + params.toString(), { credentials: 'same-origin', headers: { Accept: 'application/json' } });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.message || data.error || 'Lineage export failed.');
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
      const link = make('a', { href: url, download: 'kairos-lineage-snapshot.json' });
      document.body.append(link); link.click(); link.remove(); URL.revokeObjectURL(url);
    } catch (error) { window.alert(error.message || 'Lineage export failed.'); }
  }
  function enhance() {
    if (document.body.dataset.kairosEnhancementsDisabled === 'true') return;
    const persistedMode = q('#dataModeSelect')?.value === 'postgresql';
    if (!persistedMode) {
      document.querySelectorAll('[data-kairos-classify], [data-kairos-full-export]').forEach(el => el.remove());
      return;
    }
    document.querySelectorAll('button[data-action="asset"][data-id]').forEach(button => {
      const row = button.closest('tr');
      if (!row || q('[data-kairos-classify]', row)) return;
      const classify = make('button', { type: 'button', class: 'btn small', 'data-kairos-classify': button.dataset.id }, 'Classify');
      classify.addEventListener('click', () => openClassification(classify.dataset.kairosClassify));
      const actions = row.lastElementChild;
      if (actions) actions.append(' ', classify);
    });
    document.querySelectorAll('[data-action="export-impact"]').forEach(button => {
      if (q('[data-kairos-full-export]', button.parentElement)) return;
      const exportButton = make('button', { type: 'button', class: 'btn small', 'data-kairos-full-export': 'true' }, 'Export full snapshot JSON');
      exportButton.addEventListener('click', exportSnapshot);
      button.after(exportButton);
    });
  }
  const observer = new MutationObserver(enhance);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', enhance, { once: true }); else enhance();
})();