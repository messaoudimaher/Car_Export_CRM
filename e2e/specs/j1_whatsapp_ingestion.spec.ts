import { test, expect } from "@playwright/test";
import { setupMockApiRoutes, MOCK_TENANT_A_USER } from "../helpers/test-fixtures";

/**
 * Journey J1: Inbound WhatsApp Inquiry Ingestion & System Thread Creation (TASK-1903).
 * Architecture References: docs/user-journeys.md Section 3 (Journey J1)
 */
test.describe("Journey J1: WhatsApp Message Ingestion & Customer Creation", () => {
  test.beforeEach(async ({ page }) => {
    await setupMockApiRoutes(page, MOCK_TENANT_A_USER);
  });

  test("ingests inbound WhatsApp message and binds to customer profile", async ({ page }) => {
    await page.goto("/");

    // Verify inbox thread list displays the customer name and phone number
    const customerHeader = page.locator("text=Mohamed Ben Ali");
    await expect(customerHeader).toBeVisible();

    // Verify inbound message snippet is displayed in thread item
    const messageSnippet = page.locator("text=Bonjour, je cherche une Golf 8 TDI 2021");
    await expect(messageSnippet).toBeVisible();

    // Verify FCR eligibility badge is displayed
    const fcrBadge = page.locator("text=FCR").first();
    await expect(fcrBadge).toBeVisible();
  });
});
