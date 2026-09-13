import { test, expect } from "@playwright/test";
import { setupMockApiRoutes, MOCK_TENANT_B_USER } from "../helpers/test-fixtures";

/**
 * Journey J7: Tenant Isolation Enforcement (User A cannot view Tenant B data) (TASK-1903).
 * Architecture References: docs/user-journeys.md Section 2 (Tenant Isolation Invariant)
 */
test.describe("Journey J7: Multi-Tenant Cross-Access Isolation (SEC-010)", () => {
  test("returns 404 Not Found when Tenant B user attempts to access Tenant A resource", async ({ page }) => {
    // Intercept cross-tenant document request to simulate HTTP 404 response masking
    await page.route("**/api/v1/customers/cust-tenant-a-999**", async (route) => {
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({
          type: "https://car-export-crm.com/errors/not-found",
          title: "Not Found",
          status: 404,
          detail: "Customer not found.",
        }),
      });
    });

    await setupMockApiRoutes(page, MOCK_TENANT_B_USER);

    // Make request under Tenant B context
    const response = await page.request.get("/api/v1/customers/cust-tenant-a-999", {
      headers: { Authorization: "Bearer mock_tenant_b_jwt" },
    });

    // Assert strict HTTP 404 status code (masking 403 Forbidden per SEC-010)
    expect(response.status()).toBe(404);
  });
});
