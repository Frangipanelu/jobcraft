import { defineConfig, devices } from '@playwright/test';

const BACKEND_URL = 'http://localhost:8000';
const FRONTEND_URL = 'http://localhost:5173';

/**
 * Playwright E2E 配置（FE-ROUTE-03）。
 *
 * 启动方式：`npx playwright test`（自动通过 webServer 启动 vite dev server，proxy → 8000）。
 * 前置条件：后端已运行在 8000。
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: FRONTEND_URL,
    screenshot: 'only-on-failure',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: 'npx vite --config vite.e2e.config.ts --port 5173',
    port: 5173,
    reuseExistingServer: true,
    timeout: 30_000,
  },
});
