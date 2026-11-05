import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

/**
 * Guards the navigation contract between the dashboard shell and the standalone
 * ingestion page.  Ingestion is intentionally a separate document (it boots on
 * its own without the dashboard's React shell), so the only thing keeping the
 * two navigable from each other is this markup and the `?view=` bootstrap.
 */
const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const read = (file) => readFileSync(resolve(frontendRoot, file), 'utf8');

describe('ingestion navigation', () => {
  it('exposes a dashboard sidebar entry for ingestion', () => {
    const shell = read('src/main.jsx');
    expect(shell).toContain('href="/ingestion.html"');
    expect(shell).toContain('Ingestion &amp; sources');
  });

  it('gives the ingestion page the dashboard sidebar with links back to every section', () => {
    const page = read('ingestion.html');
    expect(page).toContain('class="app-shell"');
    expect(page).toContain('class="sidebar"');
    expect(page).toContain('aria-label="Main navigation"');
    // Every dashboard section the page links back to must resolve through the
    // SPA's `?view=` bootstrap rather than sending the user to a dead URL.
    for (const view of ['overview', 'assets', 'lineage', 'observatory', 'evidence']) {
      expect(page).toContain(`href="/?view=${view}"`);
    }
    expect(page).toContain('src="/ingestion.js');
  });

  it('lets the dashboard open a requested view from the URL', () => {
    const app = read('app.js');
    expect(app).toContain("new URLSearchParams(location.search).get('view')");
    expect(app).toContain('if(requestedView&&P[requestedView])S.view=requestedView');
  });

  it('loads the catalog mapping module before the dashboard app', () => {
    const auth = read('auth.js');
    const mapping = auth.indexOf("'/catalog-graph.js");
    const app = auth.indexOf("'/app.js");
    expect(mapping).toBeGreaterThan(-1);
    expect(app).toBeGreaterThan(mapping);
  });
});

describe('catalog provenance and graph behavior', () => {
  it('does not expose a demo data mode', () => {
    const shell = read('src/main.jsx');
    expect(shell).not.toContain('data-mode-switch="demo"');
    expect(read('app.js')).not.toContain("S.dataMode='demo'");
  });

  it('requires authentication and has no anonymous preview handler', () => {
    expect(read('auth.js')).not.toContain("message.type === 'demo-preview'");
    expect(read('auth-stitch.html')).not.toContain('Preview dashboard with sample data');
  });

  it('starts catalog collections empty until the API returns records', () => {
    expect(read('app.js')).toContain('const A=[],E=[],V=[],R=[],Q=[];');
  });

  it('derives graph columns from the tested mapping module', () => {
    const app = read('app.js');
    expect(app).toContain('assignLayers(AV,E,{groupBy:S.graphGroup})');
    expect(app).toContain("id=\"graphGroup\"");
  });

  it('does not hijack the ingestion link, so the URL survives a refresh', () => {
    const auth = read('auth.js');
    expect(auth).not.toContain("closest('a[href=\"/ingestion.html\"]')");
  });
});
