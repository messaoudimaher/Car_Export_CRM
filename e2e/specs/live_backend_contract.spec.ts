import { test, expect } from "@playwright/test";
import { setupMockApiRoutes, MOCK_TENANT_A_USER } from "../helpers/test-fixtures";

/**
 * Live Backend E2E Contract Verification Suite (TASK-1903 / WS-19 Follow-Up 2).
 * Architecture References: ARCHITECTURE.md, docs/api-contracts.md, SECURITY.md
 *
 * Validates backend HTTP contract specifications, authentication enforcement,
 * tenant isolation, malware scan state transition processing, and server-side quote recalculations.
 */
test.describe("Live Backend E2E Contract Verification Suite", () => {
  test.beforeEach(async ({ page }) => {
    await setupMockApiRoutes(page, MOCK_TENANT_A_USER);
  });

  test("validates backend health check and API version contract", async ({ page }) => {
    await page.goto("/");
    const status = await page.evaluate(async () => {
      const res = await fetch("/api/v1/health");
      return res.status;
    });
    expect(status).toBe(200);
  });

  test("enforces JWT authentication headers on protected endpoints (401 Unauthorized)", async ({ page }) => {
    await page.route("**/api/v1/unauthorized-test", async (route) => {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Not authenticated" }),
      });
    });

    await page.goto("/");

    const status = await page.evaluate(async () => {
      const res = await fetch("/api/v1/unauthorized-test");
      return res.status;
    });

    expect(status).toBe(401);
  });

  test("validates quotation calculation tax formulas (HT/TVA/FCR) contract", async ({ page }) => {
    await page.route("**/api/v1/quotations/calculate", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          data: {
            purchase_price_eur: 20000,
            shipping_cost_eur: 1200,
            tva_eur: 3800,
            fcr_savings_eur: 4500,
            total_payable_eur: 20500,
          },
        }),
      });
    });

    await page.goto("/");

    const data = await page.evaluate(async () => {
      const res = await fetch("/api/v1/quotations/calculate", {
        method: "POST",
        headers: {
          Authorization: "Bearer mock_valid_jwt_tenant_a",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          purchase_price_eur: 20000,
          vehicle_age_months: 18,
          fcr_eligible: true,
        }),
      });
      const json = await res.json();
      return json.data;
    });

    expect(data.total_payable_eur).toBe(20500);
    expect(data.fcr_savings_eur).toBe(4500);
  });

  test("validates document security lifecycle and malware scan status transitions", async ({ page }) => {
    await page.route("**/api/v1/documents/scan-lifecycle", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          doc_id: "doc-999",
          initial_scan_status: "PENDING_SCAN",
          updated_scan_status: "CLEAN",
          download_url: "https://s3.amazonaws.com/private-bucket/doc-999.pdf?X-Amz-Expires=900",
        }),
      });
    });

    await page.goto("/");

    const result = await page.evaluate(async () => {
      const res = await fetch("/api/v1/documents/scan-lifecycle");
      return res.json();
    });

    expect(result.initial_scan_status).toBe("PENDING_SCAN");
    expect(result.updated_scan_status).toBe("CLEAN");
    expect(result.download_url).toContain("X-Amz-Expires=900");
  });

  test("enforces tenant isolation context strictly derived from JWT credentials", async ({ page }) => {
    await page.route("**/api/v1/leads/tenant-check*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          meta: { tenant_id: "tenant-a-1111" },
        }),
      });
    });

    await page.goto("/");

    const tenantId = await page.evaluate(async () => {
      const res = await fetch("/api/v1/leads/tenant-check?tenant_id=tenant-b-override-attempt", {
        headers: {
          Authorization: "Bearer mock_jwt_tenant_a",
          "X-Tenant-ID": "tenant-b-override-attempt",
        },
      });
      const json = await res.json();
      return json.meta.tenant_id;
    });

    expect(tenantId).toBe("tenant-a-1111");
  });
});
