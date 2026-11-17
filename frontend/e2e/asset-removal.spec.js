import { expect, test } from '@playwright/test';

/**
 * End-to-end browser test for the Asset Removal workflow and dialog interactions.
 * Validates visual dialog rendering, warning copy, button states, cancellation,
 * mock API execution, toast notifications, and error handling.
 */
test.describe('Asset Removal UI & Workflow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    // Wait for React shell to mount
    await expect(page.locator('#root')).not.toBeEmpty();

    // Prevent unauthenticated authScreen overlay from intercepting pointer events during test
    await page.addStyleTag({
      content: '#authScreen { display: none !important; pointer-events: none !important; z-index: -9999 !important; }',
    });

    await page.evaluate(() => {
      const auth = document.getElementById('authScreen');
      if (auth) auth.hidden = true;
      const shell = document.querySelector('.app-shell');
      if (shell) shell.hidden = false;
    });
  });

  test('loads asset-removal module and exposes KairosAssetRemoval on window', async ({ page }) => {
    await page.addScriptTag({ url: '/asset-removal.js?v=1' });
    const hasModule = await page.evaluate(() => typeof window.KairosAssetRemoval === 'object');
    expect(hasModule).toBe(true);
  });

  test('opens removal modal with visual warnings and danger button on action', async ({ page }) => {
    await page.addScriptTag({ url: '/asset-removal.js?v=1' });

    // Open removal dialog programmatically
    await page.evaluate(() => {
      window.KairosAssetRemoval.openRemovalDialog({
        id: 'c87f0171-8bc4-411a-a5c9-9434e32049e2',
        name: 'raw_enterprise.customer_transactions',
      });
    });

    const backdrop = page.locator('#modalBackdrop');
    await expect(backdrop).toBeVisible();

    const title = page.locator('#modalTitle');
    await expect(title).toHaveText('Remove asset from active catalog?');

    const form = page.locator('#assetRemovalForm');
    await expect(form).toBeVisible();
    await expect(form).toContainText('raw_enterprise.customer_transactions');
    await expect(form).toContainText('This hides the asset from normal catalog views');

    const cancelBtn = form.locator('[data-action="close-modal"]');
    await expect(cancelBtn).toBeVisible();
    await expect(cancelBtn).toHaveText('Cancel');

    const submitBtn = form.locator('button[type="submit"]');
    await expect(submitBtn).toBeVisible();
    await expect(submitBtn).toHaveText('Remove from catalog');
    await expect(submitBtn).toHaveClass(/danger/);
  });

  test('cancels and closes the removal modal on Cancel button click', async ({ page }) => {
    await page.addScriptTag({ url: '/asset-removal.js?v=1' });

    await page.evaluate(() => {
      window.KairosAssetRemoval.openRemovalDialog({
        id: 'asset-test-cancel',
        name: 'staging.orders',
      });
    });

    const backdrop = page.locator('#modalBackdrop');
    await expect(backdrop).toBeVisible();

    // Click Cancel
    await page.locator('#assetRemovalForm [data-action="close-modal"]').click();
    await expect(backdrop).toBeHidden();
  });

  test('successfully submits removal, shows toast, and hides dialog', async ({ page }) => {
    await page.addScriptTag({ url: '/asset-removal.js?v=1' });

    // Mock DELETE endpoint
    await page.route('**/api/v1/assets/*', async (route) => {
      if (route.request().method() === 'DELETE') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ok: true,
            asset_id: 'asset-to-remove',
            removed: true,
            message: 'Asset removed from the active catalog.',
          }),
        });
      } else {
        await route.continue();
      }
    });

    await page.evaluate(() => {
      window.KairosAssetRemoval.openRemovalDialog({
        id: 'asset-to-remove',
        name: 'analytics.fct_daily_revenue',
      });
    });

    const backdrop = page.locator('#modalBackdrop');
    await expect(backdrop).toBeVisible();

    // Submit removal
    await page.locator('#assetRemovalForm button[type="submit"]').click();

    // Dialog should close
    await expect(backdrop).toBeHidden();

    // Toast notification should appear
    const toast = page.locator('#toastRegion .toast');
    await expect(toast).toBeVisible();
    await expect(toast).toContainText('Asset removed from the active catalog');
  });

  test('displays error message when removal fails without closing dialog', async ({ page }) => {
    await page.addScriptTag({ url: '/asset-removal.js?v=1' });

    // Mock 403 Forbidden response
    await page.route('**/api/v1/assets/*', async (route) => {
      if (route.request().method() === 'DELETE') {
        await route.fulfill({
          status: 403,
          contentType: 'application/json',
          body: JSON.stringify({
            ok: false,
            detail: 'Only workspace owners and admins can remove assets.',
          }),
        });
      } else {
        await route.continue();
      }
    });

    await page.evaluate(() => {
      window.KairosAssetRemoval.openRemovalDialog({
        id: 'protected-asset',
        name: 'executive.kpi_revenue',
      });
    });

    const backdrop = page.locator('#modalBackdrop');
    await expect(backdrop).toBeVisible();

    // Submit removal
    await page.locator('#assetRemovalForm button[type="submit"]').click();

    // Dialog remains visible with error message
    await expect(backdrop).toBeVisible();
    const alertMessage = page.locator('#assetRemovalMessage');
    await expect(alertMessage).toBeVisible();
    await expect(alertMessage).toHaveText('Only workspace owners and admins can remove assets.');

    // Submit button re-enabled
    const submitBtn = page.locator('#assetRemovalForm button[type="submit"]');
    await expect(submitBtn).toBeEnabled();
    await expect(submitBtn).toHaveText('Remove from catalog');
  });
});
