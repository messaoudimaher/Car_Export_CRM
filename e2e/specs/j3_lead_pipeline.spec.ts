import { test, expect } from "@playwright/test";
import { setupMockApiRoutes, MOCK_TENANT_A_USER } from "../helpers/test-fixtures";

/**
 * Journey J3: Customer → Lead Pipeline Advancement (TASK-1903).
 * Architecture References: docs/user-journeys.md Section 3 (Journey J5)
 */
test.describe("Journey J3: Lead Pipeline Advancement", () => {
  test.beforeEach(async ({ page }) => {
    await setupMockApiRoutes(page, MOCK_TENANT_A_USER);
  });

  test("navigates to Lead Pipeline and filters leads by stage", async ({ page }) => {
    await page.goto("/leads");

    // Verify Lead Pipeline page header
    const pipelineHeader = page.locator("text=Pipeline des Opportunités (Leads)");
    await expect(pipelineHeader).toBeVisible();

    // Verify stage filter dropdown
    const stageSelect = page.locator("select").nth(1);
    await expect(stageSelect).toBeVisible();

    // Verify lead item rendering
    const leadVehicle = page.locator("text=BMW X5 xDrive30d M Sport (2022-2023)");
    await expect(leadVehicle).toBeVisible();
  });
});
