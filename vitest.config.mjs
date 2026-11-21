/**
 * Repo-root Vitest configuration.
 *
 * `frontend/vitest.config.js` scopes the unit suite when Vitest is started from
 * `frontend/`. A run started at the repo root has no config of its own, so
 * Vitest auto-collects every `*.spec.js` it can find — including the Playwright
 * suite in `frontend/e2e/`, whose files then blow up on import
 * ("Playwright Test did not expect test() to be called here") and turn a green
 * unit run into three failed test files.
 *
 * Keeping the browser suite in Playwright and the unit suite in Vitest is the
 * rule; this file enforces it wherever the command is started.
 */
export default {
  test: {
    environment: 'node',
    include: ['frontend/__tests__/**/*.test.js'],
    exclude: ['**/node_modules/**', 'frontend/e2e/**'],
  },
};
