import { defineConfig } from 'vitest/config';

/**
 * Minimal Vitest configuration for the frontend pure helpers.
 *
 * The `node` environment is used deliberately: the personalization helpers
 * under test are DOM-free, so no browser (jsdom/happy-dom) is required.
 * Tests live in `frontend/__tests__` and are picked up by the `include` glob.
 *
 * This file takes precedence over `vite.config.js` when Vitest runs, so the
 * app's build-time asset-copy plugin is not loaded during tests.
 */
export default defineConfig({
  test: {
    environment: 'node',
    include: ['__tests__/**/*.test.js'],
  },
});
