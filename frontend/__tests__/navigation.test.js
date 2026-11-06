import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

/**
 * Guards the navigation contract between the React dashboard shell, the
 * dashboard script and the standalone ingestion document.
 *
 * Ingestion is intentionally still a separate document: `auth.js` serves it
 * through the authenticated fetch so the signed-in session and bearer header
 * survive navigation. What this suite pins is that the user can always reach it
 * from the sidebar and always get back.
 */
const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const read = (file) => readFileSync(resolve(frontendRoot, file), 'utf8');

describe('ingestion navigation', () => {
  it('exposes a dashboard sidebar entry for ingestion', () => {
    const shell = read('src/main.jsx');
    expect(shell).toContain('href="/ingestion.html"');
    expect(shell).toContain('data-authenticated-ingestion-link');
    expect(shell).toMatch(/>\s*Import metadata\s*</);
  });

  it('gives the ingestion page an obvious way back to the dashboard', () => {
    const page = read('ingestion.html');
    expect(page).toContain('href="/"');
    expect(page).toMatch(/Back to Kairos dashboard/i);
    expect(page).toContain('src="/ingestion.js');
  });

  it('lets the dashboard open a requested view from the URL', () => {
    const app = read('app.js');
    expect(app).toContain("new URLSearchParams(location.search).get('view')");
    expect(app).toContain('if(requestedView&&(P[requestedView]');
    expect(app).toContain('go(requestedView)');
  });

  it('serves the ingestion page through the authenticated fetch instead of a bare link', () => {
    const auth = read('auth.js');
    expect(auth).toContain("closest('a[href=\"/ingestion.html\"]')");
    expect(auth).toContain('serveIngestion(activeSession)');
    // Reaching /ingestion.html directly with a session must also be served, so a
    // refresh keeps the user on the page rather than bouncing them out.
    expect(auth).toContain("location.pathname === '/ingestion.html'");
  });

  it('does not load a separate catalog mapping module before the dashboard', () => {
    const auth = read('auth.js');
    expect(auth).not.toContain('catalog-graph.js');
  });

  it('keeps every M4 view reachable from the sidebar', () => {
    const shell = read('src/main.jsx');
    for (const view of ['freshness', 'incidents', 'notifications', 'settings']) {
      expect(shell).toContain(`data-view="${view}"`);
    }
    // Admin has no sidebar item in the shared shell; it stays reachable by URL.
    expect(read('app.js')).toContain("admin:'Workspace administration'");
  });
});

describe('catalog data modes', () => {
  it('offers the mode control in the dashboard top bar', () => {
    const shell = read('src/main.jsx');
    expect(shell).toContain('data-mode-switch="demo"');
    expect(shell).toContain('data-mode-switch="postgresql"');
    expect(shell).toContain('Live catalog');
  });

  it('routes the mode control through the single guarded mode setter', () => {
    const app = read('app.js');
    expect(app).toContain("closest('[data-mode-switch]')");
    expect(app).toContain('function setDataMode(mode)');
    expect(app).toContain("localStorage.setItem('kairos_dataMode','postgresql')");
  });

  it('refuses to present synthetic records as the live catalog', () => {
    const app = read('app.js');
    expect(app).toContain('Demo fixture mode is not available in this build');
    expect(app).toContain('no fixture data is substituted');
  });

  it('still labels the retained demo code path as synthetic', () => {
    const app = read('app.js');
    expect(app).toContain("S.dataMode==='demo'?'DEMO PREVIEW'");
    expect(app).toContain("S.dataMode==='demo'?'Synthetic data preview.'");
    expect(app).toContain("S.dataMode==='demo'?'DEMO DATA'");
  });

  it('renders lineage from catalog rows without the retired mapper', () => {
    const app = read('app.js');
    expect(app).toContain('function lineagePage');
    expect(app).not.toContain('KairosCatalogGraph');
    expect(app).not.toContain('assignLayers(');
  });
});
