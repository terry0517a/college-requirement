import { defineConfig, devices } from '@playwright/test'

// Locally port 3000 may be taken: run with E2E_PORT=3107. CI uses the default.
const port = Number(process.env.E2E_PORT ?? 3000)

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'github' : 'line',
  use: { baseURL: `http://localhost:${port}` },
  // The production build is made beforehand (CI step / local script).
  webServer: {
    command: `npm run start -- -p ${port}`,
    port,
    reuseExistingServer: !process.env.CI,
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'Mobile', use: { ...devices['Pixel 7'] }, testMatch: 'navigation.spec.ts' },
  ],
})
