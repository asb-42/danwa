import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig(({ mode }) => ({
  plugins: [
    svelte(
      mode === 'development'
        ? {
            // In dev mode, inject CSS into JS to avoid a race condition where
            // the browser's CSS sub-request (?svelte&type=style&lang.css)
            // arrives before the Svelte compiler has cached the extracted CSS,
            // causing PostCSS to receive the raw .svelte file and fail.
            compilerOptions: { css: 'injected' },
          }
        : undefined,
    ),
  ],
  // Pre-bundle heavy client-only deps at server startup so that
  // the first navigation to a page that uses them does not
  // trigger Vite's lazy dep optimisation.  Without this, the
  // first hit on /blueprint (which imports @xyflow/svelte)
  // causes Vite to log "✨ new dependencies optimized" and
  // reload the page — and on reload the optimised chunk file
  // is not yet on disk, producing a White-Screen-Of-Death
  // ("The file does not exist at .vite/deps/chunk-*.js").
  // The fix is to declare the deps explicitly here.
  optimizeDeps: {
    include: [
      '@xyflow/svelte',
      'cytoscape',
      'elkjs/lib/elk.bundled.js',
    ],
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:7860',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:7860',
        changeOrigin: true,
      },
      '/a2a': {
        target: 'http://localhost:7860',
        changeOrigin: true,
      },
      '/.well-known': {
        target: 'http://localhost:7860',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
}));
