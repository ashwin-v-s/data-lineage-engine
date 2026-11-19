import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';

/**
 * Mobile presentation layer.
 *
 * This is chrome only: the dashboard views themselves are still rendered once,
 * by `app.js`, into the single `#mainContent` mount. Every control here
 * delegates to the element the desktop UI already uses (the sidebar's
 * `data-view` buttons, the hidden topbar's search/theme buttons and the
 * `[data-mode-switch]` control), so both experiences read and write the same
 * application state and there is no second data path.
 *
 * `app.js` announces each render as `kairos:view-changed`; the tab bar and title
 * follow that event instead of keeping their own copy of the current view.
 */
// A rotated handset (e.g. 844x390) is wider than the phone breakpoint, so the
// short-viewport/coarse-pointer arm keeps it on the mobile experience. It is
// mirrored by the media query that opens `mobile.css`.
const MOBILE_QUERY = '(max-width: 768px), (max-height: 520px) and (pointer: coarse)';

/** Bottom tabs. Each tab owns the views it represents so deep views still light up. */
const TABS = [
  { id: 'overview', label: 'Home', icon: '▫', views: ['overview'] },
  { id: 'assets', label: 'Catalog', icon: '▤', views: ['assets', 'catalog', 'search', 'products', 'asset_detail'] },
  { id: 'lineage', label: 'Lineage', icon: '⌘', views: ['lineage', 'history', 'sql', 'observatory'] },
  { id: 'evidence', label: 'Trust', icon: '🛡', views: ['evidence', 'quality', 'freshness', 'incidents', 'glossary', 'pii', 'domains', 'notifications', 'stewardship'] },
  { id: 'more', label: 'More', icon: '⋯', views: ['sources', 'runs', 'integrations', 'settings', 'admin', 'profile'] },
];

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(() => {
    try {
      return window.matchMedia(MOBILE_QUERY).matches;
    } catch (_) {
      return window.innerWidth <= 768;
    }
  });
  useEffect(() => {
    let query = null;
    try {
      query = window.matchMedia(MOBILE_QUERY);
    } catch (_) {
      return undefined;
    }
    const sync = (event) => setIsMobile(event.matches);
    if (query.addEventListener) query.addEventListener('change', sync);
    else query.addListener(sync);
    setIsMobile(query.matches);
    return () => {
      if (query.removeEventListener) query.removeEventListener('change', sync);
      else query.removeListener(sync);
    };
  }, []);
  return isMobile;
}

function readMode() {
  try {
    return window.localStorage.getItem('kairos_dataMode') === 'demo' ? 'demo' : 'postgresql';
  } catch (_) {
    return 'postgresql';
  }
}

/** Click the desktop control that owns a behaviour, so mobile adds no new logic. */
function press(id) {
  const element = document.getElementById(id);
  if (element && !element.disabled) element.click();
}

function openDrawer() {
  const sidebar = document.getElementById('sidebar');
  if (!sidebar) return;
  sidebar.classList.remove('collapsed');
  sidebar.classList.add('open');
}

function closeDrawer() {
  const sidebar = document.getElementById('sidebar');
  if (!sidebar) return;
  sidebar.classList.remove('open');
}

/** Open the account screen through the shell's own profile control. */
function openProfile() {
  const avatar = document.querySelector('.top-avatar');
  if (avatar) { avatar.click(); return; }
  const shortcut = document.querySelector('.profile-shortcut');
  if (shortcut) shortcut.click();
}

export default function MobileShell() {
  const isMobile = useIsMobile();
  const [view, setView] = useState('overview');
  const [title, setTitle] = useState('Overview');
  const [mode, setMode] = useState(readMode);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [initials, setInitials] = useState('U');
  const [drawerHost, setDrawerHost] = useState(null);

  // Publish the layout so CSS/JS share one answer to "is this a phone?".
  useEffect(() => {
    const root = document.documentElement;
    root.dataset.layout = isMobile ? 'mobile' : 'desktop';
    return () => { delete root.dataset.layout; };
  }, [isMobile]);

  useEffect(() => {
    const onView = (event) => {
      const next = event && event.detail;
      if (!next || !next.view) return;
      setView(next.view);
      setTitle(next.label || document.getElementById('breadcrumbTitle')?.textContent || 'Overview');
      setDrawerOpen(false);
    };
    const onMode = (event) => {
      const next = event && event.detail && event.detail.dataMode;
      if (next) setMode(next);
    };
    window.addEventListener('kairos:view-changed', onView);
    window.addEventListener('kairos:data-mode', onMode);
    return () => {
      window.removeEventListener('kairos:view-changed', onView);
      window.removeEventListener('kairos:data-mode', onMode);
    };
  }, []);

  // A resize into desktop clears the drawer so the sidebar is not left open.
  useEffect(() => {
    if (!isMobile) closeDrawer();
  }, [isMobile]);


  // The app bar carries the account initials the desktop avatar already shows.
  useEffect(() => {
    const read = () => {
      const text = (document.querySelector('.top-avatar')?.textContent || '').replace(/[^\w]/g, '').slice(0, 2);
      if (text) setInitials(text.toUpperCase());
    };
    read();
    window.addEventListener('kairos:auth-ready', read);
    window.addEventListener('kairos:view-changed', read);
    return () => {
      window.removeEventListener('kairos:auth-ready', read);
      window.removeEventListener('kairos:view-changed', read);
    };
  }, []);

  // The desktop topbar (which owns Help and the theme switch) is hidden on
  // phones, so those two controls move into the drawer instead of disappearing.
  // They are still the same desktop buttons: this only hosts them.
  useEffect(() => {
    if (!isMobile) { setDrawerHost(null); return undefined; }
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) return undefined;
    const host = document.createElement('div');
    host.className = 'mobile-drawer-tools';
    const brand = sidebar.querySelector('.brand');
    if (brand && brand.parentElement === sidebar) brand.after(host);
    else sidebar.prepend(host);
    setDrawerHost(host);
    return () => { host.remove(); setDrawerHost(null); };
  }, [isMobile]);

  const activeTab = TABS.find((tab) => tab.views.includes(view)) || TABS[0];

  const selectTab = (tab) => {
    if (tab.id === 'more') {
      openDrawer();
      setDrawerOpen(true);
      return;
    }
    // The sidebar owns every destination, so drive it rather than `go()`.
    const target = document.querySelector(`#sidebar .nav-item[data-view="${tab.id}"]`);
    if (target && !target.hidden) target.click();
    else {
      openDrawer();
      setDrawerOpen(true);
    }
  };

  const toggleMode = () => {
    const next = mode === 'demo' ? 'postgresql' : 'demo';
    const switchButton = document.querySelector(`[data-mode-switch="${next}"]`);
    if (switchButton && !switchButton.disabled) switchButton.click();
  };

  // Nothing at all is rendered above the phone breakpoint, so the desktop
  // document is exactly the one it was before this layer existed.
  if (!isMobile) return null;

  return (
    <>
      {(
        <header className="mobile-header" id="mobileHeader">
          <button aria-expanded={drawerOpen} aria-label="Open navigation" className="mobile-header-btn" id="mobileMenuBtn" onClick={() => { openDrawer(); setDrawerOpen(true); }} type="button">☰</button>
          <div className="mobile-title">
            <span className="mobile-brand">KAIROS</span>
            <strong id="mobileTitle">{title}</strong>
          </div>
          <button aria-label={`Data mode: ${mode === 'demo' ? 'demo preview' : 'live catalog'}. Switch mode.`} className="mobile-mode" onClick={toggleMode} type="button">{mode === 'demo' ? 'DEMO' : 'LIVE'}</button>
          <button aria-label="Search workspace" className="mobile-header-btn" onClick={() => press('globalSearchButton')} type="button">⌕</button>
          <button aria-label={`Open your account (${initials})`} className="mobile-header-btn mobile-account" onClick={openProfile} type="button">{initials}</button>
        </header>
      )}
      <div aria-hidden="true" className="mobile-scrim" onClick={() => { closeDrawer(); setDrawerOpen(false); }} />
      {drawerHost && createPortal(
        <>
          <button className="btn small" onClick={() => press('themeToggle')} type="button"><span aria-hidden="true">◴</span> Theme</button>
          <button className="btn small" onClick={() => press('helpButton')} type="button"><span aria-hidden="true">?</span> Help</button>
        </>,
        drawerHost,
      )}
      {(
        <nav aria-label="Primary" className="mobile-tabbar" id="mobileTabbar">
          {TABS.map((tab) => (
            <button
              aria-current={activeTab.id === tab.id ? 'page' : undefined}
              className="mobile-tab"
              data-tab={tab.id}
              key={tab.id}
              onClick={() => selectTab(tab)}
              type="button"
            >
              <span aria-hidden="true" className="mobile-tab-icon">{tab.icon}</span>
              <span className="mobile-tab-label">{tab.label}</span>
            </button>
          ))}
        </nav>
      )}
    </>
  );
}
