(() => {
  'use strict';

  const MAX_FILES = 500;
  const MAX_SCAN_FILE_BYTES = 2 * 1024 * 1024;
  const MAX_INGEST_FILE_BYTES = 512 * 1024;
  const MAX_TOTAL_BYTES = 25 * 1024 * 1024;
  const SUPPORTED = new Set(['.sql', '.json', '.yml', '.yaml', '.md', '.csv']);
  const ignoredDirectories = new Set(['.git', 'node_modules', '.venv', 'venv', '__pycache__']);
  const $ = (selector) => document.querySelector(selector);
  const chooseButton = $('#chooseFolderButton');
  const status = $('#folderScanStatus');
  const list = $('#folderFileList');
  const preview = $('#folderFilePreview');
  const previewButton = $('#previewLocalFileButton');
  const ingestButton = $('#ingestLocalFileButton');
  const inventoryButton = $('#importFolderInventoryButton');
  if (!chooseButton || !status || !list) return;

  let rootHandle = null;
  let files = [];
  let selectedPath = '';
  let selectedFile = null;
  let busy = false;

  const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char]);
  const extension = (path) => {
    const name = path.split('/').pop() || '';
    const dot = name.lastIndexOf('.');
    return dot < 0 ? '' : name.slice(dot).toLowerCase();
  };
  const formatBytes = (size) => size < 1024 ? `${size} B`
    : size < 1024 * 1024 ? `${(size / 1024).toFixed(1)} KB`
      : `${(size / (1024 * 1024)).toFixed(2)} MB`;
  const digest = async (file) => {
    if (!crypto?.subtle) throw new Error('Secure SHA-256 hashing is unavailable in this browser. Open Kairos on localhost or HTTPS.');
    const bytes = await file.arrayBuffer();
    const hash = await crypto.subtle.digest('SHA-256', bytes);
    return [...new Uint8Array(hash)].map((byte) => byte.toString(16).padStart(2, '0')).join('');
  };
  const setBusy = (value) => {
    busy = value;
    chooseButton.disabled = value;
    previewButton.disabled = value || !selectedFile;
    ingestButton.disabled = value || !selectedFile || !selectedFile.supported;
    inventoryButton.disabled = value || !rootHandle || !files.length;
  };

  async function walk(directory, prefix = '') {
    const entries = [];
    for await (const [name, handle] of directory.entries()) {
      if (handle.kind === 'directory') {
        if (ignoredDirectories.has(name.toLowerCase())) continue;
        entries.push(...await walk(handle, prefix ? `${prefix}/${name}` : name));
        continue;
      }
      const path = prefix ? `${prefix}/${name}` : name;
      const file = await handle.getFile();
      entries.push({ path, handle, file, size_bytes: file.size, modified_at: file.lastModified ? new Date(file.lastModified).toISOString() : null, format: extension(path).slice(1) || 'unknown', supported: SUPPORTED.has(extension(path)) });
      if (entries.length > MAX_FILES) throw new Error(`This folder has more than ${MAX_FILES} files. Select a smaller project folder.`);
    }
    return entries;
  }

  function renderList() {
    const query = ($('#folderFilter')?.value || '').trim().toLowerCase();
    const shown = files.filter((entry) => !query || `${entry.path} ${entry.format}`.toLowerCase().includes(query));
    if (!shown.length) {
      list.innerHTML = `<div class="folder-empty">${files.length ? 'No files match this filter.' : 'Choose a folder to view its file tree.'}</div>`;
      return;
    }
    list.innerHTML = `<ul class="folder-file-tree">${shown.map((entry) => {
      const depth = entry.path.split('/').length - 1;
      return `<li style="--depth:${depth}"><button class="folder-file-row" type="button" data-folder-path="${escapeHtml(entry.path)}" aria-pressed="${entry.path === selectedPath}"><span>${escapeHtml(entry.path)}</span><small>${escapeHtml(entry.format.toUpperCase())} · ${formatBytes(entry.size_bytes)}</small></button></li>`;
    }).join('')}</ul>`;
  }

  async function chooseFolder() {
    if (!('showDirectoryPicker' in window)) {
      status.textContent = 'This browser does not support secure folder selection. Use the existing single-file import or open Kairos in Edge or Chrome.';
      return;
    }
    try {
      rootHandle = await window.showDirectoryPicker({ mode: 'read' });
      setBusy(true);
      status.textContent = `Scanning the selected folder “${rootHandle.name}”…`;
      files = await walk(rootHandle);
      let total = 0;
      for (const entry of files) {
        total += entry.size_bytes;
        if (entry.size_bytes > MAX_SCAN_FILE_BYTES) {
          entry.scan_warning = `Skipped hash: file exceeds ${formatBytes(MAX_SCAN_FILE_BYTES)} scan limit`;
          continue;
        }
        if (total > MAX_TOTAL_BYTES) {
          entry.scan_warning = `Skipped hash: folder exceeds ${formatBytes(MAX_TOTAL_BYTES)} hash budget`;
          continue;
        }
        entry.sha256 = await digest(entry.file);
      }
      selectedPath = '';
      selectedFile = null;
      preview.hidden = true;
      renderList();
      const supported = files.filter((entry) => entry.supported).length;
      status.textContent = `Scanned ${files.length} files in “${rootHandle.name}”; ${supported} have supported extensions. Files are still on this computer. Nothing has been uploaded.`;
    } catch (error) {
      if (error?.name !== 'AbortError') status.textContent = `Folder scan failed: ${error.message || 'The selected folder could not be read.'}`;
    } finally {
      setBusy(false);
    }
  }

  async function selectFile(path) {
    const entry = files.find((candidate) => candidate.path === path);
    if (!entry) return;
    selectedPath = path;
    selectedFile = entry;
    renderList();
    preview.hidden = true;
    setBusy(false);
  }

  async function previewSelected() {
    if (!selectedFile) return;
    setBusy(true);
    try {
      if (selectedFile.size_bytes > MAX_SCAN_FILE_BYTES) throw new Error(`Files larger than ${formatBytes(MAX_SCAN_FILE_BYTES)} cannot be previewed in this demo.`);
      const content = await selectedFile.file.text();
      preview.hidden = false;
      preview.innerHTML = `<h3>${escapeHtml(selectedFile.path)}</h3><p>Local preview only. This content has not been sent to Kairos.</p><p>${escapeHtml(selectedFile.format.toUpperCase())} · ${formatBytes(selectedFile.size_bytes)} · SHA-256 ${escapeHtml(selectedFile.sha256 || 'not computed')}</p><pre class="folder-preview-content">${escapeHtml(content.slice(0, 60_000))}${content.length > 60_000 ? '\n… preview truncated …' : ''}</pre>`;
      status.textContent = `Previewing ${selectedFile.path}. Content remains local until you choose Ingest selected file.`;
    } catch (error) {
      status.textContent = `Preview failed: ${error.message}`;
    } finally {
      setBusy(false);
    }
  }

  function makeFileGraph(entry, content) {
    return {
      source: { kind: 'local_file', ref: `${rootHandle.name}/${entry.path}` },
      assets: [{
        id: `local-file:${entry.sha256 || entry.path}`,
        namespace: 'local-folder',
        name: entry.path.split('/').pop(),
        qualified_name: `file://${rootHandle.name}/${entry.path}`,
        type: 'file',
        kind: 'source',
        metadata: {
          path: entry.path,
          root_folder: rootHandle.name,
          format: entry.format,
          size_bytes: entry.size_bytes,
          modified_at: entry.modified_at,
          sha256: entry.sha256 || null,
          original_content: content,
          imported_by: 'user-selected local folder file',
        },
      }],
      relationships: [],
    };
  }

  async function postPreviewAndCommit(kind, filename, content) {
    const common = { kind, filename, content };
    const previewResponse = await fetch('/api/v1/ingest/preview', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(common), credentials: 'same-origin',
    });
    const previewResult = await previewResponse.json().catch(() => ({}));
    if (!previewResponse.ok || !previewResult.ok) {
      const detail = previewResult.detail;
      throw new Error(typeof detail === 'string' ? detail : detail?.message || `Preview failed (${previewResponse.status}).`);
    }
    if (!previewResult.commit_ready) throw new Error(previewResult.commit_blocker || 'Import storage is not installed.');
    status.textContent = `Preview found ${previewResult.preview.assets} asset(s). Saving selected file evidence…`;
    const response = await fetch('/api/v1/ingest/commit', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...common, idempotency_key: crypto.randomUUID() }), credentials: 'same-origin',
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || !result.ok) {
      const detail = result.detail;
      throw new Error(typeof detail === 'string' ? detail : detail?.message || `Import failed (${response.status}).`);
    }
    return result;
  }

  async function ingestSelected() {
    if (!selectedFile || !rootHandle) return;
    setBusy(true);
    try {
      if (!selectedFile.supported) throw new Error('Choose a .sql, .json, .yml, .yaml, .md, or .csv file.');
      if (selectedFile.size_bytes > MAX_INGEST_FILE_BYTES) throw new Error(`Files larger than ${formatBytes(MAX_INGEST_FILE_BYTES)} cannot be ingested in this demo because the authenticated API request has a size cap.`);
      const content = await selectedFile.file.text();
      const kind = selectedFile.format === 'sql' ? 'sql_file' : 'metadata_graph';
      const payload = kind === 'sql_file' ? content : makeFileGraph(selectedFile, content);
      const result = await postPreviewAndCommit(kind, selectedFile.path, payload);
      status.textContent = `Imported ${selectedFile.path} into this workspace (${result.summary.persisted_assets} file asset). The original content is retained in the import's raw evidence.`;
      document.dispatchEvent(new CustomEvent('kairos:local-file-imported', { detail: { importId: result.import_id, path: selectedFile.path } }));
    } catch (error) {
      status.textContent = `File ingestion failed: ${error.message || 'Unknown server error.'} No fixture data was substituted.`;
    } finally {
      setBusy(false);
    }
  }

  async function importInventory() {
    if (!rootHandle || !files.length) return;
    setBusy(true);
    try {
      const inventory = {
        source_system: 'local_folder',
        source_revision: new Date().toISOString(),
        files: files.map(({ path, size_bytes, modified_at, format, sha256 }) => ({ path, size_bytes, modified_at, format, sha256: sha256 || null })),
      };
      const result = await postPreviewAndCommit('file_inventory', `${rootHandle.name}-inventory.json`, inventory);
      status.textContent = `Imported folder inventory: ${files.length} files from “${rootHandle.name}”. Inventory records paths and metadata; it does not infer data lineage.`;
      document.dispatchEvent(new CustomEvent('kairos:local-folder-imported', { detail: { importId: result.import_id, files: files.length } }));
    } catch (error) {
      status.textContent = `Folder inventory import failed: ${error.message || 'Unknown server error.'}`;
    } finally {
      setBusy(false);
    }
  }

  chooseButton.addEventListener('click', chooseFolder);
  $('#folderFilter')?.addEventListener('input', renderList);
  list.addEventListener('click', (event) => {
    const button = event.target.closest('[data-folder-path]');
    if (button) selectFile(button.dataset.folderPath);
  });
  previewButton.addEventListener('click', previewSelected);
  ingestButton.addEventListener('click', ingestSelected);
  inventoryButton.addEventListener('click', importInventory);
})();
