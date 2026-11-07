import { expect, test } from '@playwright/test';

test('sign-in waits for server auth config before showing configuration errors', async ({ page }) => {
  let configReleased = false;
  let authRequests = 0;
  let releaseConfig;
  const configGate = new Promise((resolve) => { releaseConfig = resolve; });
  await page.route('**/api/v1/auth/config', async (route) => {
    await configGate;
    configReleased = true;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        url: 'https://kairos-auth-race.supabase.co',
        publishable_key: 'public-test-key',
        auth_disabled: false,
      }),
    });
  });
  await page.route('**/auth/v1/token*', async (route) => {
    authRequests += 1;
    await route.fulfill({
      status: 400,
      contentType: 'application/json',
      body: JSON.stringify({ msg: 'Invalid login credentials' }),
    });
  });

  await page.goto('/');
  const auth = page.frameLocator('#authFrame');
  await auth.locator('#work-email').fill('kairos-race@example.test');
  await auth.locator('#auth-token').fill('not-a-real-password');
  await auth.locator('#signin-form button[type="submit"]').click();
  await page.waitForTimeout(100);

  expect(configReleased).toBe(false);
  expect(authRequests).toBe(0);
  releaseConfig();
  await expect.poll(() => authRequests, { timeout: 10000 }).toBe(1);
  expect(configReleased).toBe(true);
});
