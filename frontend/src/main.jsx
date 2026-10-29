import React, { useEffect, useLayoutEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { flushSync } from 'react-dom';

const initialDashboardMarkup = '<div class="loading-state">Loading workspace…</div>';

function AuthScreen() {
  return (
    <section aria-label="Kairos authentication" className="auth-screen" id="authScreen">
      <iframe id="authFrame" src="/auth-stitch.html?mode=login" title="Sign in to Kairos" />
    </section>
  );
}

function Sidebar() {
  return (
    <aside className="sidebar" id="sidebar">
      <div className="brand">
        <img alt="Kairos logo" className="brand-logo" src="/logo.png" />
        <div><strong>KAIROS</strong><small>METADATA PLATFORM</small></div>
        <button aria-label="Close navigation" className="icon-btn mobile-close" id="closeNav">×</button>
        <button aria-label="Toggle sidebar" className="icon-btn" id="sidebarToggleBtn" style={{ marginLeft: 'auto', width: 28, height: 28, fontSize: 12 }} title="Collapse sidebar">◀</button>
      </div>
      <nav aria-label="Main navigation" className="nav-list nav-groups">
        <button className="nav-item nav-primary active" data-view="overview"><span className="nav-icon">▫</span>Home</button>
        <div className="nav-group" data-nav-group="catalog">
          <button aria-expanded="false" className="nav-item nav-primary" data-view="assets"><span className="nav-icon">▤</span>Catalog<span aria-hidden="true" className="nav-chevron">⌄</span></button>
          <div className="nav-sublist" hidden>
            <button className="nav-item nav-child" data-action="open-all-assets">All assets</button>
            <button className="nav-item nav-child" data-view="catalog">Catalog structure</button>
            <button className="nav-item nav-child" data-view="search">Catalog search</button>
            <button className="nav-item nav-child" data-view="products">Data Products <span className="nav-tag">NEW</span></button>
          </div>
        </div>
        <div className="nav-group" data-nav-group="lineage">
          <button aria-expanded="false" className="nav-item nav-primary" data-view="lineage"><span className="nav-icon">⌘</span>Lineage<span aria-hidden="true" className="nav-chevron">⌄</span></button>
          <div className="nav-sublist" hidden>
            <button className="nav-item nav-child" data-view="lineage">Visual explorer</button>
            <button className="nav-item nav-child" data-view="history">Time travel</button>
            <button className="nav-item nav-child" data-view="sql">SQL analysis</button>
            <button className="nav-item nav-child" data-view="observatory">3D observatory <span className="nav-tag">BETA</span></button>
          </div>
        </div>
        <div className="nav-group" data-nav-group="operations">
          <button aria-expanded="false" className="nav-item nav-primary" data-view="runs"><span className="nav-icon">↻</span>Operations<span aria-hidden="true" className="nav-chevron">⌄</span></button>
          <div className="nav-sublist" hidden>
            <a className="nav-item nav-child" href="/ingestion.html">Import metadata</a>
            <button className="nav-item nav-child" data-view="runs">Pipeline runs</button>
          </div>
        </div>
        <div className="nav-group" data-nav-group="trust">
          <button aria-expanded="false" className="nav-item nav-primary" data-view="evidence"><span className="nav-icon">🛡</span>Trust &amp; governance<span aria-hidden="true" className="nav-chevron">⌄</span></button>
          <div className="nav-sublist" hidden>
            <button className="nav-item nav-child" data-view="evidence">Evidence &amp; reasoning</button>
            <button className="nav-item nav-child" data-view="quality">Data quality</button>
            <button className="nav-item nav-child" data-view="incidents">Incident console <span className="nav-tag">NEW</span></button>
            <button className="nav-item nav-child" data-view="stewardship">Stewardship <span className="nav-tag">NEW</span></button>
          </div>
        </div>
        <div className="nav-group" data-nav-group="settings">
          <button aria-expanded="false" className="nav-item nav-primary" data-view="integrations"><span className="nav-icon">⚙</span>System<span aria-hidden="true" className="nav-chevron">⌄</span></button>
          <div className="nav-sublist" hidden>
            <button className="nav-item nav-child" data-view="integrations">Integrations &amp; API</button>
            <button className="nav-item nav-child" data-view="settings">Preferences</button>
          </div>
        </div>
      </nav>
      <div className="sidebar-bottom">
        <div className="health-card">
          <div className="health-top"><span className="status-dot" /><strong>Workspace mode</strong><span className="health-live" id="sidebarModeBadge">DEMO</span></div>
          <p id="sidebarModeDescription">Synthetic sample records; not production data.</p>
          <div className="health-foot"><span>Data source</span><b id="sidebarSourceLabel">Demo</b></div>
        </div>
        <button aria-label="Open user profile" className="user-row profile-shortcut" data-view="profile" type="button">
          <span className="avatar profile-avatar">U</span><span className="user-copy"><strong className="profile-display-name">Workspace user</strong><small>Signed-in account</small></span><span aria-hidden="true" className="more">•••</span>
        </button>
      </div>
    </aside>
  );
}

function DashboardContent() {
  const [markup, setMarkup] = useState(initialDashboardMarkup);
  useLayoutEffect(() => {
    window.kairosRenderDashboardView = (html) => flushSync(() => setMarkup(html));
    return () => { delete window.kairosRenderDashboardView; };
  }, []);
  return <main className="content" id="mainContent"><div dangerouslySetInnerHTML={{ __html: markup }} /></main>;
}

function DashboardShell() {
  return (
    <div className="app-shell" hidden>
      <Sidebar />
      <div className="main-area">
        <header className="topbar">
          <button aria-label="Open navigation" className="icon-btn menu-toggle" id="openNav">☰</button>
          <div className="breadcrumbs"><span>Workspace</span><b>/</b><strong id="breadcrumbTitle">Overview</strong></div>
          <div className="top-actions">
            <div aria-label="Authenticated data source" className="data-mode-control"><span>DATA</span><strong>CONNECTED CATALOG</strong></div>
            <div className="environment" id="environmentBadge"><span className="status-dot" />DEMO DATA</div>
            <button aria-label="Switch between light and dark theme" className="top-icon" id="themeToggle" title="Switch light / dark">◴</button>
            <button aria-label="Search workspace (Ctrl+K)" className="top-icon" id="globalSearchButton" title="Search (Ctrl+K)">⌕</button>
            <button aria-label="Help" className="top-icon" id="helpButton" title="Help">?</button>
            <button aria-label="Open user profile" className="top-avatar profile-avatar" data-view="profile" type="button">JS</button>
          </div>
        </header>
        <DashboardContent />
        <footer className="footer"><span><i className="status-dot" /> Kairos metadata engine <b>·</b> <span id="footerModeLabel">Demo mode</span></span><span>Evidence-first lineage <b>·</b> v0.1 prototype <b>·</b> build v305</span></footer>
      </div>
    </div>
  );
}

function App() {
  useEffect(() => {
    const script = document.createElement('script');
    script.src = '/auth.js?v=2';
    script.async = true;
    script.onerror = () => console.error('Kairos authentication bootstrap could not be loaded.');
    document.body.appendChild(script);
  }, []);
  return (
    <>
      <AuthScreen />
      <a className="skip-link" href="#mainContent">Skip to main content</a>
      <DashboardShell />
      <div aria-live="polite" className="toast-region" id="toastRegion" />
      <div className="modal-backdrop" hidden id="modalBackdrop">
        <section aria-labelledby="modalTitle" aria-modal="true" className="modal" role="dialog">
          <div className="modal-head"><div><h2 id="modalTitle">Details</h2></div><button aria-label="Close dialog" className="icon-btn" id="modalClose">×</button></div>
          <div id="modalBody" />
        </section>
      </div>
    </>
  );
}

createRoot(document.getElementById('root')).render(<App />);
