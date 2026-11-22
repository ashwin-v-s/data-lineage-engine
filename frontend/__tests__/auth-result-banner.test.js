import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

/**
 * Regression guard for the sign-in feedback path.
 *
 * `showAuthResult(message, kind)` reveals `#form-alert-banner` and then, for a
 * successful sign-up, switches the panel to sign-in mode. It used to read a
 * bare `form` variable that existed only in the caller's scope, so every call
 * threw `ReferenceError: form is not defined` at the line *before*
 * `banner.classList.remove('hidden')`. The banner stayed hidden, the toast
 * never updated, and no authentication error or success was ever shown.
 */
const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const source = readFileSync(resolve(frontendRoot, 'auth-stitch.html'), 'utf8');

function extractFunction(name) {
  const start = source.indexOf(`function ${name}(`);
  expect(start, `${name}() must exist in auth-stitch.html`).toBeGreaterThan(-1);
  const open = source.indexOf('{', start);
  let depth = 0;
  for (let index = open; index < source.length; index += 1) {
    if (source[index] === '{') depth += 1;
    else if (source[index] === '}') {
      depth -= 1;
      if (depth === 0) return source.slice(start, index + 1);
    }
  }
  throw new Error(`Could not find the end of ${name}()`);
}

describe('auth feedback banner', () => {
  const body = extractFunction('showAuthResult');

  it('accepts the operation that produced the result as a parameter', () => {
    expect(body).toMatch(/function showAuthResult\(\s*message\s*,\s*kind\s*=\s*'error'\s*,\s*form\s*=\s*''\s*\)/);
  });

  it('never reads an undeclared `form` binding', () => {
    // Every `form` reference must be the parameter, so no bare identifier can
    // throw before the banner is revealed.
    expect(body).toContain("form=''");
    expect(body).not.toMatch(/const\s+form\b|let\s+form\b|var\s+form\b/);
  });

  it('reveals the banner after the result is applied, so the message is visible', () => {
    const switchIndex = body.indexOf("form==='signup'");
    const revealIndex = body.indexOf("banner.classList.remove('hidden')");
    expect(switchIndex).toBeGreaterThan(-1);
    expect(revealIndex).toBeGreaterThan(switchIndex);
  });

  it('is called with the operation from the message handler', () => {
    expect(source).toContain("showAuthResult(message,ok?'success':'error',form)");
  });
});
