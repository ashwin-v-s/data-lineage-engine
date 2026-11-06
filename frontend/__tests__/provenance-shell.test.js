import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

/**
 * These assertions pin the *integration contract* between the React shell
 * (`src/main.jsx`) and the dashboard script (`app.js`), plus the provenance
 * behaviour that survived the merge with origin/main. They read source text
 * because both files are browser-only scripts with no import surface.
 */

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const read = (relativePath) => readFileSync(resolve(frontendRoot, relativePath), 'utf8');

const shell = read('src/main.jsx');
const app = read('app.js');
const auth = read('auth.js');
const viteConfig = read('vite.config.js');
const freshnessComponent = read('src/components/FreshnessView.jsx');

/** Replace JS line comments so assertions cannot match commented-out markup. */
const withoutComments = (source) => source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');

const appCode = withoutComments(app);

describe('dashboard shell contract', () => {
  it('mounts dashboard markup into the single #mainContent host', () => {
    expect(shell).toContain('id="mainContent"');
    expect(shell).toContain('window.kairosRenderDashboardView = (html)');
    expect(shell).toContain('window.kairosShowLiveView');
    // The shell owns the fallback content, so app.js must not write into it directly.
    expect(appCode).toContain('if(window.kairosRenderDashboardView)window.kairosRenderDashboardView(');
  });

  it('exposes one provenance banner host the dashboard reuses instead of appending banners', () => {
    expect(shell).toContain('id="dataSourceBannerContainer"');
    expect(appCode).toContain("const bannerHost=$('#dataSourceBannerContainer')");
    expect(appCode).toContain('bannerHost.replaceChildren(banner)');
  });

  it('passes both the live view and the selected asset over the bridge', () => {
    // The contract Kiro integrates against: window.kairosShowLiveView(view, assetId).
    expect(appCode).toContain('window.kairosShowLiveView(liveView,S.selected)');
    expect(appCode).toContain('window.kairosSelectedAssetId=S.selected');
  });

  it('does not build dashboard fallback markup for a React-owned view', () => {
    expect(appCode).toContain("window.kairosShowLiveView&&LIVE_VIEWS.includes(S.view)?S.view:null");
    expect(appCode).toContain("window.kairosRenderDashboardView(liveView?'':pages[S.view]())");
  });

  it('keeps the dashboard fallback renderers available for a shell without React', () => {
    expect(appCode).toContain('function freshnessPage()');
    expect(appCode).toContain('function incidentsPage()');
    expect(appCode).toContain("else $('#mainContent').innerHTML=pages[S.view]()");
  });

  it('removes the duplicate capability renderer: React owns the panel', () => {
    expect(appCode).not.toContain('function assetCapabilitiesMarkup');
    // Capability lookups still gate profile tabs, so they are retained.
    expect(appCode).toContain('function assetCapabilityEntry');
    expect(appCode).toContain('function loadAssetCapabilities');
    expect(shell).toContain('AssetCapabilitiesPanel');
  });

  it('renders the M4 React views for the bridged view names', () => {
    expect(shell).toContain("liveView === 'freshness'");
    expect(shell).toContain('FreshnessView');
    expect(shell).toContain("liveView === 'incidents'");
    expect(shell).toContain('IncidentsView');
    expect(shell).toContain('GovernanceView');
  });

  it('keeps the M4 views and settings reachable in the sidebar', () => {
    for (const view of ['notifications', 'settings', 'freshness', 'incidents', 'sources', 'integrations']) {
      expect(shell).toContain(`data-view="${view}"`);
    }
    expect(appCode).toContain("['sources','freshness','notifications','glossary','domains','admin']");
  });

  it('keeps workspace administration reachable even without a sidebar entry', () => {
    // The shared sidebar has no admin item; the view must still resolve from the
    // URL (?view=admin) and keep its dashboard renderer and loader.
    expect(appCode).toContain("admin:'Workspace administration'");
    expect(appCode).toContain('admin:adminPage');
    expect(appCode).toContain("if(S.view==='admin')loadMembers()");
  });

  it('loads asset capabilities when the asset detail view renders', () => {
    // loadAssetCapabilities must be called during render, not just defined
    expect(appCode).toContain("loadAssetCapabilities(S.selected)");
    // The call must be gated by the asset_detail view and not a live view
    expect(appCode).toContain("if(S.view==='asset_detail'&&!liveView)loadAssetCapabilities(S.selected)");
  });
});

describe('provenance status in the dashboard script', () => {
  it('starts as NOT CONNECTED until an authenticated catalog request succeeds', () => {
    expect(app).toMatch(/catalogStatus:'loading'/);
    expect(appCode).toContain("localStorage.setItem('kairos_catalogStatus','loading')");
    // No demo records may be loaded at boot; the catalog is the only source.
    expect(appCode).toContain("S.dataMode='postgresql';localStorage.setItem('kairos_dataMode','postgresql')");
  });

  it('labels loading, ready and error catalog states distinctly', () => {
    // Provenance labels are now React-owned; app.js dispatches catalogStatus.
    expect(appCode).toContain("catalogStatus:S.catalogStatus");
    expect(appCode).toContain("S.catalogStatus='error'");
  });

  it('announces the catalog status so React views can resolve the data mode', () => {
    expect(appCode).toContain("new CustomEvent('kairos:data-mode',{detail:{dataMode:S.dataMode,catalogStatus:S.catalogStatus}})");
  });

  it('clears catalog records and reports the failure instead of substituting demo data', () => {
    expect(appCode).toContain("S.catalogStatus='error'");
    expect(appCode).toContain('S.dataError=err?.message');
    expect(appCode).toContain('A.splice(0,A.length)');
  });

  it('routes profile save to the browser-local implementation exactly once', () => {
    const handlers = app.match(/else if\(a==='save-profile'\)/g) || [];
    expect(handlers).toHaveLength(1);
    expect(appCode).toContain("localStorage.setItem('kairos_profileName'");
    expect(appCode).not.toContain("else if(a==='save-profile'){}");
  });

  it('opens a view requested through the URL for every known section', () => {
    expect(appCode).toContain("new URLSearchParams(location.search).get('view')");
    expect(appCode).toContain("P[requestedView]||['catalog','assets'].includes(requestedView)");
  });

  it('refuses to switch to demo data silently', () => {
    expect(appCode).toContain("button.dataset.modeSwitch==='postgresql'");
    expect(appCode).toContain('Demo fixture mode is not available in this build');
    expect(appCode).toContain('function setDataMode(mode)');
  });
});

describe('freshness evidence vocabulary', () => {
  it('distinguishes an explicit UNAVAILABLE reference from a missing one', () => {
    expect(read('src/views/freshness.js')).toContain("evidenceRef?.kind === 'UNAVAILABLE'");
    expect(freshnessComponent).toContain("item.evidenceSource === 'RUNTIME'");
  });

  it('requests warn thresholds that satisfy the 80% API rule', () => {
    const freshnessView = read('src/views/freshness.js');
    expect(freshnessView).toMatch(/warn_after_minutes: 60,\s*\n\s*error_after_minutes: 75,/);
    expect(appCode).toContain('name="error_after_minutes" class="field-input" type="number" min="2" value="75"');
  });
});

describe('legacy runtime assets', () => {
  it('loads app.js with a cache-busting version and never loads the retired mapper', () => {
    expect(auth).toMatch(/\/app\.js\?v=\d+/);
    expect(auth).not.toContain('catalog-graph.js');
    expect(appCode).not.toContain('KairosCatalogGraph');
    expect(viteConfig).not.toContain('catalog-graph.js');
  });

  it('ships the ingestion page, styles and dashboard script in the built frontend', () => {
    for (const asset of ["'app.js'", "'auth.js'", "'ingestion.html'", "'ingestion.js'", "'layout.css'", "'styles.neo.css'"]) {
      expect(viteConfig).toContain(asset);
    }
  });

  it('includes personalization assets in the build output', () => {
    expect(viteConfig).toContain("'personalization.js'");
    expect(viteConfig).toContain("'personalization.css'");
  });

  it('keeps the ingestion link interception that serves the page through the authenticated fetch', () => {
    expect(auth).toContain("closest('a[href=\"/ingestion.html\"]')");
    expect(auth).toContain("fetch('/ingestion.html')");
  });
});


describe('React provenance ownership and data-mode consumption', () => {
  it('consumes catalogStatus from the event, not the nonexistent liveRequestSucceeded', () => {
    expect(shell).toContain('catalogStatus: detail.catalogStatus');
    expect(shell).not.toContain('liveRequestSucceeded: detail.liveRequestSucceeded');
  });

  it('initializes as loading so the shell never starts in LIVE', () => {
    expect(shell).toContain("catalogStatus: 'loading'");
  });

  it('renders provenance labels from data-mode state, not from window.kairosDemoPreview', () => {
    expect(shell).toContain('dataModeDescription(dataMode)');
    expect(shell).toContain('sourceLabel(dataMode)');
    // No hardcoded window.kairosDemoPreview ternaries for provenance labels
    expect(shell).not.toContain('window.kairosDemoPreview ? "DEMO FIXTURE"');
    expect(shell).not.toContain('window.kairosDemoPreview ? "Demo fixture"');
    expect(shell).not.toContain('window.kairosDemoPreview ? "Not connected"');
  });

  it('React owns the five provenance label nodes; app.js does not write to them', () => {
    // app.js must not write to these five nodes (it dispatches the event instead)
    expect(appCode).not.toContain("$('#environmentBadge')");
    expect(appCode).not.toContain("$('#sidebarModeBadge')");
    expect(appCode).not.toContain("$('#sidebarModeDescription')");
    expect(appCode).not.toContain("$('#sidebarSourceLabel')");
    expect(appCode).not.toContain("$('#footerModeLabel')");
  });

  it('does not route admin or settings through React live-view routing', () => {
    // The GovernanceView dispatch list must not include admin or settings
    expect(shell).toContain("['glossary', 'pii', 'domains', 'products', 'notifications'].includes(liveView)");
    // admin and settings nav entries exist (app.js owns the pages)
    expect(shell).toContain('data-view="admin"');
    expect(shell).toContain('data-view="settings"');
  });

  it('keeps the loadAssetCapabilities call intact in the render flow', () => {
    expect(appCode).toContain("if(S.view==='asset_detail'&&!liveView)loadAssetCapabilities(S.selected)");
  });
});
