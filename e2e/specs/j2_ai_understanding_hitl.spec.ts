import { test, expect } from "@playwright/test";
import { setupMockApiRoutes, MOCK_TENANT_A_USER } from "../helpers/test-fixtures";

/**
 * Journey J2: AI Understanding Extraction → Human Confirmation Boundary (HITL) (TASK-1903).
 * Architecture References: docs/user-journeys.md Section 3 (Journey J2, J3, J4)
 */
test.describe("Journey J2: AI Extraction & Human Confirmation Boundary", () => {
  test.beforeEach(async ({ page }) => {
    await setupMockApiRoutes(page, MOCK_TENANT_A_USER);
  });

  test("displays AI extraction card with confidence score and enforces HITL confirmation boundary", async ({ page }) => {
    await page.goto("/");

    // Verify AI Understanding Card displays extracted vehicle model
    const extractedModel = page.locator("text=BMW X5 xDrive30d").first();
    await expect(extractedModel).toBeVisible();

    // Verify confidence score badge
    const confidenceBadge = page.locator("text=94% Confiance");
    await expect(confidenceBadge).toBeVisible();

    // Verify HITL Non-Authoritative notice tag (INV-003)
    const hitlTag = page.locator("text=INV-003 HITL");
    await expect(hitlTag).toBeVisible();

    // Click "Confirmer & Appliquer au Lead" human confirmation button
    const confirmButton = page.getByRole("button", { name: /confirmer/i });
    await expect(confirmButton).toBeVisible();
    await confirmButton.click();
  });
});
