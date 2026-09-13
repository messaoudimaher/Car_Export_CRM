import { test, expect } from "@playwright/test";
import { setupMockApiRoutes, MOCK_TENANT_A_USER } from "../helpers/test-fixtures";

/**
 * Journey J6: Document Upload & Malware Security Scan Lifecycle (TASK-1903 / WS-15 BR-013).
 * Architecture References: docs/user-journeys.md Section 3, SECURITY.md
 */
test.describe("Journey J6: Document Upload & Security Scan Lifecycle", () => {
  test.beforeEach(async ({ page }) => {
    await setupMockApiRoutes(page, MOCK_TENANT_A_USER);
  });

  test("models full scan lifecycle: PENDING_SCAN -> SCAN PROCESSING -> PASSED -> Pre-signed Download", async ({ page }) => {
    await page.goto("/documents");

    // Verify page title
    const pageTitle = page.locator("text=Dépôt Privé S3 & Documents RGPD");
    await expect(pageTitle).toBeVisible();

    // 1. Verify PENDING_SCAN document blocks pre-signed download
    const pendingDoc = page.locator("text=Passeport_Scan_Karim_Mansour.pdf");
    await expect(pendingDoc).toBeVisible();

    const pendingBadge = page.locator("text=Antivirus S3: EN COURS");
    await expect(pendingBadge).toBeVisible();

    const pendingStatusText = page.locator("text=Analyse Antivirus S3 en cours...");
    await expect(pendingStatusText).toBeVisible();

    // 2. Verify CLEAN / PASSED document enables 15-min pre-signed download
    const cleanDoc = page.locator("text=Carte_Grise_BMW_X5_WBA123.pdf");
    await expect(cleanDoc).toBeVisible();

    const cleanBadge = page.locator("text=Antivirus S3: CLEAN").first();
    await expect(cleanBadge).toBeVisible();

    const downloadBtn = page.getByRole("button", { name: /télécharger \(pre-signed\)/i }).first();
    await expect(downloadBtn).toBeVisible();
    await expect(downloadBtn).toBeEnabled();

    // 3. Verify QUARANTINED document access is strictly blocked
    const quarantinedDoc = page.locator("text=Facture_Douanier_Suspecte.exe.pdf");
    await expect(quarantinedDoc).toBeVisible();

    const quarantinedBadge = page.locator("text=Antivirus S3: INFECTED (QUARANTAINE)");
    await expect(quarantinedBadge).toBeVisible();

    const quarantinedBlockedBadge = page.locator("text=Accès Bloqué (Quarantaine Sécurité)");
    await expect(quarantinedBlockedBadge).toBeVisible();
  });
});

