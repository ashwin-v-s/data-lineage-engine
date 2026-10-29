import { copyFileSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { defineConfig } from 'vite';

const frontendRoot = import.meta.dirname;
const runtimeFiles = [
  'app.js',
  'auth.js',
  'auth-stitch.html',
  'auth-stitch.css',
  'auth.css',
  'assets.css',
  'layout.css',
  'styles.css',
  'styles.neo.css',
  'stewardship.css',
  'ingestion.html',
  'ingestion.js',
  'observatory.js',
  'stewardship.js',
  'pii-lineage-enhancements.js',
  'logo.png',
  'accent-bg.png',
  'empty-state.png',
  'supabase-icon-green-transparent.svg',
];

export default defineConfig({
  publicDir: false,
  plugins: [{
    name: 'kairos-copy-legacy-runtime-assets',
    closeBundle() {
      const output = resolve(frontendRoot, 'dist');
      mkdirSync(output, { recursive: true });
      for (const file of runtimeFiles) {
        copyFileSync(resolve(frontendRoot, file), resolve(output, file));
      }
    },
  }],
  server: {
    host: '127.0.0.1',
    port: 3000,
    strictPort: true,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/ingestion.html': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
  build: {
    outDir: resolve(frontendRoot, 'dist'),
    emptyOutDir: true,
    sourcemap: true,
  },
});
