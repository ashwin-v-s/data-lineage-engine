import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright config for the browser-level app-shell smoke test.
 *
 * Server: the app is booted with the project's own Vite dev server
 * (`npm run dev` -> `vite`), which serves `frontend/index.html` verbatim,
 * including its `<script type="module" src="/src/main.jsx">` and
 * `<script type="module" src="/personalization.js">` entry points. Vite is the
 * server that actually serves the real shell; `scripts/run_ui.py` instead
 * builds the bundle and serves it from the Python backend on port 8000, which
 * also requires the FastAPI app (and Supabase config) to be running.
 *
 * The suite is deliberately backend-free: `vite.config.js` proxies `/api/*`
 * to `http://127.0.0.1:8000`, but no backend exists in CI. That is fine for a
 * shell smoke test — the React root mounts synchronously and `auth.js` handles
 * the unreachable config endpoint gracefully.
 */
export default defineConfig({
  // Explicitly scope collection to e2e/ so Playwright can never pick up the
  // Vitest files under `__tests__/**` (`*.test.js`).
  testDir: './e2e',
  testMatch: '**/*.spec.js',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: 'http://127.0.0.1:3000',
    headless: true,
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://127.0.0.1:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    stdout: 'pipe',
    stderr: 'pipe',
  },
});
