import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
// `vitest/config` re-exports `defineConfig` from Vite with the `test` field
// typed, so this one file covers both the dev server and Vitest.
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
  server: {
    proxy: {
      // Backend runs unproxied on 8000 (see docs/architecture.md §2.3);
      // this keeps frontend and API on a single origin in development,
      // so no CORS configuration is needed.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // `/health` is deliberately unprefixed on the backend (see
      // docs/architecture.md §5), so it needs its own proxy entry
      // alongside `/api`.
      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
