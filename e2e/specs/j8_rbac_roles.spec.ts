import { test, expect } from "@playwright/test";
import { setupMockApiRoutes, MOCK_LOGISTICS_USER, MOCK_TENANT_A_USER } from "../helpers/test-fixtures";

/**
 * Journey J8: Role-based UI Behavior (Sales Agent vs Logistics Agent views) (TASK-1903).
 * Architecture References: docs/user-journeys.md Section 1.2 (Permission Matrix)
 */
test.describe("Journey J8: Role-Based Access Control (RBAC) UI Behavior", () => {
  test("Sales Agent UI presents full chat dispatch and quote creation controls", async ({ page }) => {
    await setupMockApiRoutes(page, MOCK_TENANT_A_USER);
    await page.goto("/");

    // Verify Sales Agent has access to Quote Generator
    const quoteButton = page.getByRole("button", { name: /générer devis fcr/i });
    await expect(quoteButton).toBeVisible();
  });

  test("Logistics Agent UI prioritizes document compliance and sourcing views", async ({ page }) => {
    await setupMockApiRoutes(page, MOCK_LOGISTICS_USER);
    await page.goto("/documents");

    // Verify Logistics Agent sees document repository view
    const docHeader = page.locator("text=Dépôt Privé S3 & Documents RGPD");
    await expect(docHeader).toBeVisible();
  });
});
