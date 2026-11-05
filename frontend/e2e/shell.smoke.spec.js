import { expect, test } from '@playwright/test';

/**
 * Browser-level smoke test for the Kairos application shell.
 *
 * Scope: ONLY the shell that `frontend/index.html` boots — the React root
 * (`src/main.jsx`) and the `personalization.js` module. This suite must pass
 * with no backend and no Supabase instance, so every assertion targets markup
 * that is rendered deterministically on load and never data fetched from the
 * API. There is intentionally no auth bypass: the shell is auth-gated and the
 * tests assert on the always-present shell containers (attached, not visible).
 */
test.describe('Kairos app shell', () => {
  test('mounts the React shell without uncaught page errors', async ({ page }) => {
    const pageErrors = [];
    page.on('pageerror', (error) => pageErrors.push(error.message));

    await page.goto('/');

    // React root is mounted and populated: `createRoot(...).render(<App />)`
    // runs synchronously, so these nodes exist regardless of auth/backend state.
    await expect(page.locator('#root')).not.toBeEmpty();

    // Shell containers rendered by the React shell. `#authScreen` is the
    // auth-gated landing surface; `#sidebar` and `#mainContent` live inside
    // `.app-shell` (hidden until authenticated) and are asserted as attached
    // rather than visible, so no credentials or backend are required.
    await expect(page.locator('#authScreen')).toBeAttached();
    await expect(page.locator('#sidebar')).toBeAttached();
    await expect(page.locator('#mainContent')).toBeAttached();

    // No uncaught exception is thrown while the shell boots. Network failures
    // against the (absent) backend are handled by auth.js and are not page
    // errors, so this assertion stays deterministic without a backend.
    expect(pageErrors).toEqual([]);
  });

  test('loads the personalization.js module without error', async ({ page }) => {
    const pageErrors = [];
    page.on('pageerror', (error) => pageErrors.push(error.message));

    await page.goto('/');

    // The module self-registers `window.kairosPersonalization` on load (see the
    // `typeof window !== 'undefined'` block at the end of personalization.js).
    // We assert the module executed, not any backend-derived panel content.
    await expect
      .poll(() => page.evaluate(() => typeof window.kairosPersonalization))
      .toBe('object');

    expect(pageErrors).toEqual([]);
  });
});
