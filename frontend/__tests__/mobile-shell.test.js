import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

/**
 * Guards the two-presentation contract.
 *
 * One application, one backend: the desktop shell stays as it is, the phone gets
 * extra chrome from `MobileShell.jsx`, and `mobile.css` is scoped so it can
 * never reach the desktop layout. These assertions are static on purpose — they
 * catch a component that stops being mounted or a stylesheet that starts
 * leaking, without needing a browser.
 */
const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const read = (file) => readFileSync(resolve(frontendRoot, file), 'utf8');

describe('device-adaptive presentation', () => {
  it('mounts the mobile shell inside the single dashboard shell', () => {
    const shell = read('src/main.jsx');
    expect(shell).toContain("import MobileShell from './components/MobileShell.jsx';");
    expect(shell).toContain('<MobileShell />');
    // The desktop structure is still the one and only content mount.
    expect(shell).toContain('className="sidebar" id="sidebar"');
    expect(shell).toContain('id="mainContent"');
    expect(shell.match(/id="mainContent"/g)).toHaveLength(1);
  });

  it('loads the mobile stylesheet after every desktop stylesheet', () => {
    const html = read('index.html');
    const links = [...html.matchAll(/<link href="([^"]+)"/g)].map((match) => match[1]);
    expect(links.some((href) => href.startsWith('/mobile.css'))).toBe(true);
    expect(links[links.length - 1]).toMatch(/^\/mobile\.css/);
    expect(read('vite.config.js')).toContain("'mobile.css'");
  });

  it('never applies mobile rules above the phone breakpoint', () => {
    const css = read('mobile.css');
    // Remove comments, then every media block and keyframe block. If anything
    // with a declaration survives, a rule escaped its breakpoint guard.
    const topLevel = css
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/@media[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}/g, '')
      .replace(/@keyframes[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}/g, '');
    expect(topLevel).not.toMatch(/\{/);
    expect(css).not.toMatch(/@media[^{]*min-width:\s*10[0-9][0-9]px[^{]*\{/);
  });

  it('delegates mobile navigation to the existing controls', () => {
    const shell = read('src/components/MobileShell.jsx');
    // No second router: the tabs click the sidebar's own destinations.
    expect(shell).toContain('.nav-item[data-view=');
    expect(shell).toContain("press('globalSearchButton')");
    expect(shell).toContain("press('themeToggle')");
    expect(shell).toContain('[data-mode-switch=');
    expect(shell).not.toContain('fetch(');
  });

  it('reports the phone navigation as expanded, matching what is visible', () => {
    // mobile.css force-shows every group's children on a phone, so neither the
    // React shell nor app.js may announce them as collapsed.
    expect(read('src/main.jsx')).toContain('aria-expanded={expanded}');
    expect(read('app.js')).toContain('mobileNavPresentation');
  });

  it('publishes the rendered view for the mobile shell to follow', () => {
    const app = read('app.js');
    expect(app).toContain("new CustomEvent('kairos:view-changed'");
    expect(read('src/components/MobileShell.jsx')).toContain("addEventListener('kairos:view-changed'");
  });
});
