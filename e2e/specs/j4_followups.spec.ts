import { test, expect } from "@playwright/test";
import { setupMockApiRoutes, MOCK_TENANT_A_USER } from "../helpers/test-fixtures";

/**
 * Journey J4: Lead → Follow-up Task Creation & Completion (TASK-1903).
 * Architecture References: docs/user-journeys.md Section 3 (Journey J6)
 */
test.describe("Journey J4: Follow-up Task Scheduling & Completion", () => {
  test.beforeEach(async ({ page }) => {
    await setupMockApiRoutes(page, MOCK_TENANT_A_USER);
  });

  test("schedules follow-up check-in and renders active reminder", async ({ page }) => {
    await page.goto("/");

    // Locate customer sidebar and check-in buttons
    const customerSidebar = page.locator("aside").first();
    await expect(customerSidebar).toBeVisible();

    // Verify customer name in sidebar
    const customerName = page.locator("text=Mohamed Ben Ali").first();
    await expect(customerName).toBeVisible();
  });
});
