import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E Test Suite Configuration (TASK-1903).
 * Architecture References: docs/user-journeys.md, docs/frontend-architecture.md Section 31
 */
export default defineConfig({
  testDir: "./specs",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [["html", { open: "never" }], ["list"]],

  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:5173",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "firefox",
      use: { ...devices["Desktop Firefox"] },
    },
    {
      name: "webkit",
      use: { ...devices["Desktop Safari"] },
    },
  ],

  webServer: {
    command: "npx.cmd vite --port 5173",
    cwd: "../src/frontend",
    port: 5173,
    reuseExistingServer: true,
  },
});
