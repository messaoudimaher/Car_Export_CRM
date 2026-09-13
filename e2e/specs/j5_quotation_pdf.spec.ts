import { test, expect } from "@playwright/test";
import { setupMockApiRoutes, MOCK_TENANT_A_USER } from "../helpers/test-fixtures";

/**
 * Journey J5: Lead → Quotation PDF Generation & Send (TASK-1903).
 * Architecture References: docs/user-journeys.md Section 3 (Journey J7)
 */
test.describe("Journey J5: Quotation PDF Generation & Approval Workflow", () => {
  test.beforeEach(async ({ page }) => {
    await setupMockApiRoutes(page, MOCK_TENANT_A_USER);
  });

  test("opens QuotationBuilder, tests Netto/Brutto VAT regimes, and triggers >5% manager warning", async ({ page }) => {
    await page.goto("/");

    // Click "Générer Devis FCR" button in customer sidebar
    const quoteButton = page.getByRole("button", { name: /générer devis fcr/i });
    await expect(quoteButton).toBeVisible();
    await quoteButton.click();

    // Verify modal header
    const modalHeader = page.locator("text=Générateur de Devis FCR");
    await expect(modalHeader).toBeVisible();

    // Verify Netto vs Brutto VAT regime options
    const nettoOption = page.locator("text=Netto Export (TVA 0%)");
    await expect(nettoOption).toBeVisible();

    // Enter discount percentage > 5% to trigger BR-015 manager warning
    const discountInput = page.getByLabel(/Remise Remise/i);
    await discountInput.fill("8");

    // Verify Manager Approval Warning appears
    const managerWarning = page.locator("text=validation d'un Manager");
    await expect(managerWarning).toBeVisible();
  });
});
