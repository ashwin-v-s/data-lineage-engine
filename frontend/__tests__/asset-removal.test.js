import { beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const assetRemovalSource = readFileSync(resolve(frontendRoot, 'asset-removal.js'), 'utf8');
const appSource = readFileSync(resolve(frontendRoot, 'app.js'), 'utf8');
const authSource = readFileSync(resolve(frontendRoot, 'auth.js'), 'utf8');

function createFakeDom() {
  const elements = new Map();
  const listeners = new Map();

  function makeElement(id = '', tag = 'div') {
    const el = {
      id,
      tagName: tag.toUpperCase(),
      hidden: true,
      innerHTML: '',
      textContent: '',
      dataset: {},
      disabled: false,
      children: [],
      append(child) {
        this.children.push(child);
      },
      remove() {
        const parent = this.parentElement;
        if (parent) {
          parent.children = parent.children.filter((c) => c !== this);
        }
      },
      focus: vi.fn(),
      querySelector(selector) {
        if (selector === '[type="submit"]') {
          return this.submitBtn || { disabled: false, textContent: 'Remove from catalog' };
        }
        if (selector === '[data-action="close-modal"]') {
          return this.cancelBtn || { textContent: 'Cancel' };
        }
        return null;
      },
      querySelectorAll() {
        return [];
      },
    };
    return el;
  }

  const toastRegion = makeElement('toastRegion');
  const modalBackdrop = makeElement('modalBackdrop');
  const modalTitle = makeElement('modalTitle');
  const modalBody = makeElement('modalBody');
  const modalClose = makeElement('modalClose');

  elements.set('toastRegion', toastRegion);
  elements.set('modalBackdrop', modalBackdrop);
  elements.set('modalTitle', modalTitle);
  elements.set('modalBody', modalBody);
  elements.set('modalClose', modalClose);

  const doc = {
    getElementById(id) {
      if (!elements.has(id)) {
        elements.set(id, makeElement(id));
      }
      return elements.get(id);
    },
    createElement(tag) {
      return makeElement('', tag);
    },
    addEventListener(event, cb) {
      if (!listeners.has(event)) listeners.set(event, []);
      listeners.get(event).push(cb);
    },
    removeEventListener(event, cb) {
      if (listeners.has(event)) {
        listeners.set(event, listeners.get(event).filter((f) => f !== cb));
      }
    },
    dispatchEvent(event) {
      const cbs = listeners.get(event.type) || [];
      cbs.forEach((cb) => cb(event));
      return true;
    },
  };

  return { doc, elements, listeners };
}

describe('KairosAssetRemoval contract and source wiring', () => {
  it('is wired into auth.js script loading list', () => {
    expect(authSource).toContain("'/asset-removal.js?v=1'");
  });

  it('renders removal button in catalog asset table when in postgresql mode', () => {
    expect(appSource).toContain('data-action="remove-asset"');
    expect(appSource).toContain("S.dataMode==='postgresql'?'<button class=\"btn small danger\" type=\"button\" data-action=\"remove-asset\"");
  });

  it('renders removal button in asset profile details when in postgresql mode', () => {
    expect(appSource).toContain("S.dataMode==='postgresql'?'<button class=\"btn danger\" type=\"button\" data-action=\"remove-asset\"");
    expect(appSource).toContain('Remove from catalog');
  });

  it('handles kairos:asset-removed custom event in app.js without full reload', () => {
    expect(appSource).toContain("document.addEventListener('kairos:asset-removed'");
    expect(appSource).toContain('A.splice(idx,1)');
  });
});

describe('KairosAssetRemoval runtime behavior', () => {
  let fakeDom;
  let moduleExports;

  beforeEach(() => {
    fakeDom = createFakeDom();
    globalThis.document = fakeDom.doc;
    globalThis.window = {
      setTimeout: (fn) => fn(),
      location: { reload: vi.fn() },
    };
    globalThis.CustomEvent = class {
      constructor(type, init = {}) {
        this.type = type;
        this.detail = init.detail;
      }
    };

    // Evaluate asset-removal.js with fake DOM
    const fn = new Function('root', assetRemovalSource);
    fn(globalThis);
    moduleExports = globalThis.KairosAssetRemoval;
  });

  it('exports expected API methods', () => {
    expect(moduleExports).toBeDefined();
    expect(typeof moduleExports.openRemovalDialog).toBe('function');
    expect(typeof moduleExports.closeRemovalDialog).toBe('function');
    expect(typeof moduleExports.submitRemoval).toBe('function');
    expect(typeof moduleExports.escapeHtml).toBe('function');
  });

  it('escapes special characters', () => {
    expect(moduleExports.escapeHtml('<script>')).toBe('&lt;script&gt;');
    expect(moduleExports.escapeHtml('"hello"')).toBe('&quot;hello&quot;');
  });

  it('opens removal dialog and unhides backdrop', () => {
    moduleExports.openRemovalDialog({ id: 'dataset-123', name: 'raw_enterprise.customers' });
    const backdrop = fakeDom.doc.getElementById('modalBackdrop');
    const title = fakeDom.doc.getElementById('modalTitle');
    const body = fakeDom.doc.getElementById('modalBody');

    expect(backdrop.hidden).toBe(false);
    expect(title.textContent).toBe('Remove asset from active catalog?');
    expect(body.innerHTML).toContain('raw_enterprise.customers');
    expect(body.innerHTML).toContain('data-asset-id="dataset-123"');
    expect(body.innerHTML).toContain('data-action="close-modal"');
    expect(body.innerHTML).toContain('Remove from catalog');
  });

  it('closes removal dialog and hides backdrop', () => {
    moduleExports.openRemovalDialog({ id: 'dataset-123', name: 'raw_enterprise.customers' });
    expect(fakeDom.doc.getElementById('modalBackdrop').hidden).toBe(false);

    moduleExports.closeRemovalDialog();
    expect(fakeDom.doc.getElementById('modalBackdrop').hidden).toBe(true);
  });

  it('submits removal successfully, closes dialog, and dispatches kairos:asset-removed', async () => {
    const eventHandler = vi.fn();
    fakeDom.doc.addEventListener('kairos:asset-removed', eventHandler);

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ok: true, removed: true, asset_id: 'dataset-123' }),
    });

    const submit = { disabled: false, textContent: 'Remove from catalog' };
    const message = { textContent: '' };

    moduleExports.openRemovalDialog({ id: 'dataset-123', name: 'raw_enterprise.customers' });
    const result = await moduleExports.submitRemoval('dataset-123', { submit, message });

    expect(result.ok).toBe(true);
    expect(fakeDom.doc.getElementById('modalBackdrop').hidden).toBe(true);
    expect(eventHandler).toHaveBeenCalledTimes(1);
    expect(eventHandler.mock.calls[0][0].detail).toEqual({ assetId: 'dataset-123' });

    const toastRegion = fakeDom.doc.getElementById('toastRegion');
    expect(toastRegion.children.length).toBeGreaterThan(0);
    expect(toastRegion.children[0].textContent).toContain('Asset removed from the active catalog');
  });

  it('handles removal errors, sets error message, and restores submit button state', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ ok: false, detail: 'Forbidden: Admin role required' }),
    });

    const submit = { disabled: false, textContent: 'Remove from catalog' };
    const message = { textContent: '' };

    moduleExports.openRemovalDialog({ id: 'dataset-err', name: 'staging.sensitive' });

    await expect(
      moduleExports.submitRemoval('dataset-err', { submit, message })
    ).rejects.toThrow('Forbidden: Admin role required');

    expect(message.textContent).toBe('Forbidden: Admin role required');
    expect(submit.disabled).toBe(false);
    expect(submit.textContent).toBe('Remove from catalog');
  });
});
