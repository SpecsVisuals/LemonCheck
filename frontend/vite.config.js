/**
 * vite.config.js
 *
 * Vite build configuration for LemonCheck frontend.
 *
 * Key settings:
 * - React plugin for JSX transform + HMR
 * - Path alias: '@' maps to '/src' for clean imports (e.g., '@/lib/supabase')
 * - Dev server proxies /api requests to FastAPI backend on port 8000
 *   so CORS isn't an issue during local development
 */

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
});
