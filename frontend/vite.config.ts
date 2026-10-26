import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Vite 5 configuration. Source: https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Dev only. `api/client.ts` calls a relative `/api/v1/...`, so without this the
    // browser would ask the Vite origin for it and get the SPA fallback instead of the
    // API. Added by T14 so the views can actually be read in a browser.
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
});
