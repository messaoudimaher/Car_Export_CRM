import { test, expect } from "@playwright/test";
import { setupMockApiRoutes, MOCK_TENANT_A_USER } from "../helpers/test-fixtures";

/**
 * Journey J6: Document Upload → S3 Pre-signed Preview (TASK-1903).
 * Architecture References: docs/user-journeys.md Section 3 (Journey J10)
 */
test.describe("Journey J6: Document Upload & S3 Pre-Signed Preview", () => {
  test.beforeEach(async ({ page }) => {
    await setupMockApiRoutes(page, MOCK_TENANT_A_USER);
  });

  test("navigates to documents page and displays uploaded document scan status", async ({ page }) => {
    await page.goto("/documents");

    // Verify page title
    const pageTitle = page.locator("text=Dépôt Privé S3 & Documents RGPD");
    await expect(pageTitle).toBeVisible();

    // Verify document item in table
    const docItem = page.locator("text=carte_grise_golf8.pdf");
    await expect(docItem).toBeVisible();

    // Verify SHA-256 malware scan status badge (CLEAN)
    const scanBadge = page.locator("text=CLEAN");
    await expect(scanBadge).toBeVisible();

    // Verify 15-minute pre-signed download action button
    const downloadBtn = page.getByRole("button", { name: /aperçu 15 min/i });
    await expect(downloadBtn).toBeVisible();
  });
});
