import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright E2E test configuration.
 * Tests run against the FastAPI backend serving the built frontend at :8000.
 * For local dev, the backend must be running. In CI, it's started before tests.
 */
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['html', { open: 'never' }],
    ['list'],
  ],
  use: {
    baseURL: 'http://localhost:8000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    // -----------------------------------------------------------------------
    // E2E + Contract tests — run on both browsers (exclude visual & a11y)
    // -----------------------------------------------------------------------
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
      testIgnore: /(visual|a11y)\/.*\.(visual|a11y)\.spec\.js$/,
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
      testIgnore: /(visual|a11y)\/.*\.(visual|a11y)\.spec\.js$/,
    },
    // -----------------------------------------------------------------------
    // Visual regression — Chromium only (screenshots are browser-specific)
    // -----------------------------------------------------------------------
    {
      name: 'visual-chromium',
      use: { ...devices['Desktop Chrome'] },
      testMatch: /visual\/.*\.visual\.spec\.js$/,
    },
    // -----------------------------------------------------------------------
    // Accessibility — Chromium only (axe-core is browser-independent)
    // -----------------------------------------------------------------------
    {
      name: 'a11y-chromium',
      use: { ...devices['Desktop Chrome'] },
      testMatch: /a11y\/.*\.a11y\.spec\.js$/,
    },
  ],
  /* Start the backend before running tests (local dev) */
  webServer: {
    command: 'cd .. && uv run uvicorn debate_engine.main:app --host 0.0.0.0 --port 8000',
    url: 'http://localhost:8000/health',
    reuseExistingServer: !process.env.CI,
    timeout: 30000,
  },
});
