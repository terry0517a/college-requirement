import { fileURLToPath } from 'node:url'
import { configDefaults, defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  resolve: {
    tsconfigPaths: true,
    // `server-only` throws outside the Next bundler; tests run server code directly.
    alias: { 'server-only': fileURLToPath(new URL('./tests/empty-module.ts', import.meta.url)) },
  },
  test: {
    environment: 'node',
    globals: true,
    exclude: [...configDefaults.exclude, 'e2e/**'],
    setupFiles: ['./tests/setup-db.ts'],
  },
})
