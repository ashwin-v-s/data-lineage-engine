import { cpSync, copyFileSync, existsSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { defineConfig } from 'vite';

const frontendRoot = import.meta.dirname;
const runtimeFiles = [
  'app.js',
  'asset-removal.js',
  'auth.js',
  'auth-stitch.html',
  'auth-stitch.css',
  'auth.css',
  'assets.css',
  'layout.css',
  'mobile.css',
  'styles.css',
  'styles.neo.css',
  'stewardship.css',
  'ingestion.html',
  'ingestion.js',
  'folder-ingestion.js',
  'observatory.js',
  'stewardship.js',
  'evidence-semantics.js',
  'lineage-investigation.js',
  'lineage-edge-inspector.js',
  'personalization.js',
  'personalization.css',
  'logo.png',
  'accent-bg.png',
  'empty-state.png',
  'supabase-icon-green-transparent.svg',
  'vendors/three.min.js',
  'vendors/chart.umd.min.js',
];

export default defineConfig({
  publicDir: false,
  plugins: [{
    name: 'kairos-copy-legacy-runtime-assets',
    closeBundle() {
      const output = resolve(frontendRoot, 'dist');
      mkdirSync(output, { recursive: true });
      for (const file of runtimeFiles) {
        const destination = resolve(output, file);
        mkdirSync(dirname(destination), { recursive: true });
        copyFileSync(resolve(frontendRoot, file), destination);
      }
      /* The observatory's HDR/PBR assets are served by the classic scripts, so
         they ship verbatim rather than through the module graph. */
      const sceneAssets = resolve(frontendRoot, 'scene-assets');
      if (existsSync(sceneAssets)) {
        cpSync(sceneAssets, resolve(output, 'scene-assets'), { recursive: true });
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
