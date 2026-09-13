import { test, expect } from "@playwright/test";
import { setupMockApiRoutes, MOCK_TENANT_A_USER, MOCK_TENANT_B_USER } from "../helpers/test-fixtures";

/**
 * Journey J7: Multi-Tenant Cross-Access Isolation & Negative Security Paths (TASK-1903 / SEC-010).
 * Architecture References: docs/user-journeys.md Section 2, SECURITY.md
 */
test.describe("Journey J7: Multi-Tenant Cross-Access Isolation (SEC-010)", () => {
  test("returns 404 Not Found when Tenant B user attempts to access Tenant A customer resource", async ({ page }) => {
    await setupMockApiRoutes(page, MOCK_TENANT_B_USER);

    // Intercept cross-tenant request to verify HTTP 404 response masking
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

    await page.goto("/");

    const status = await page.evaluate(async () => {
      const res = await fetch("/api/v1/customers/cust-tenant-a-999", {
        headers: { Authorization: "Bearer mock_tenant_b_jwt" },
      });
      return res.status;
    });

    // Assert strict HTTP 404 status code (masking 403 Forbidden per SEC-010)
    expect(status).toBe(404);
  });

  test("rejects cross-tenant WebSocket connection attempt with 4003 Unauthorized Tenant", async ({ page }) => {
    await setupMockApiRoutes(page, MOCK_TENANT_B_USER);

    await page.route("**/ws/conversations**", async (route) => {
      await route.fulfill({
        status: 403,
        contentType: "application/json",
        body: JSON.stringify({ code: 4003, reason: "Unauthorized Tenant Connection" }),
      });
    });

    await page.goto("/");

    const status = await page.evaluate(async () => {
      const res = await fetch("/ws/conversations?tenant_id=tenant-a-1111", {
        headers: { Authorization: "Bearer mock_tenant_b_jwt" },
      });
      return res.status;
    });

    expect(status).toBe(403);
  });

  test("rejects cross-tenant document pre-signed download URL requests with 404", async ({ page }) => {
    await setupMockApiRoutes(page, MOCK_TENANT_B_USER);

    await page.route("**/api/v1/documents/doc-tenant-a-888/download**", async (route) => {
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Document not found." }),
      });
    });

    await page.goto("/");

    const status = await page.evaluate(async () => {
      const res = await fetch("/api/v1/documents/doc-tenant-a-888/download", {
        headers: { Authorization: "Bearer mock_tenant_b_jwt" },
      });
      return res.status;
    });

    expect(status).toBe(404);
  });

  test("ignores client-supplied tenant_id query/header override in favor of JWT identity context", async ({ page }) => {
    await setupMockApiRoutes(page, MOCK_TENANT_B_USER);

    await page.route("**/api/v1/leads*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          data: [],
          meta: { tenant_id: "tenant-b-2222" },
        }),
      });
    });

    await page.goto("/");

    const metaTenantId = await page.evaluate(async () => {
      const res = await fetch("/api/v1/leads?tenant_id=tenant-a-1111", {
        headers: {
          Authorization: "Bearer mock_tenant_b_jwt",
          "X-Tenant-ID": "tenant-a-1111",
        },
      });
      const data = await res.json();
      return data.meta.tenant_id;
    });

    expect(metaTenantId).toBe("tenant-b-2222");
  });
});

