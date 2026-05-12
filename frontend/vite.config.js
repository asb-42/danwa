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
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
}));
