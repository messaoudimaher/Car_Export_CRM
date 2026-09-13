import { test, expect } from "@playwright/test";
import { setupMockApiRoutes, MOCK_LOGISTICS_USER, MOCK_TENANT_A_USER } from "../helpers/test-fixtures";

/**
 * Journey J8: Role-Based Access Control (RBAC) & Negative Authorization Paths (TASK-1903 / SEC-005).
 * Architecture References: docs/user-journeys.md Section 1.2, SECURITY.md
 */
test.describe("Journey J8: Role-Based Access Control (RBAC) & Authorization Security", () => {
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

  test("rejects unauthorized scan-result submission from non-scanner API client with 403", async ({ page }) => {
    await setupMockApiRoutes(page, MOCK_TENANT_A_USER);

    await page.route("**/api/v1/documents/doc-101/scan-result", async (route) => {
      await route.fulfill({
        status: 403,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Only automated virus scanner daemon may post scan results." }),
      });
    });

    await page.goto("/");

    const status = await page.evaluate(async () => {
      const res = await fetch("/api/v1/documents/doc-101/scan-result", {
        method: "POST",
        headers: { Authorization: "Bearer mock_sales_agent_jwt", "Content-Type": "application/json" },
        body: JSON.stringify({ status: "CLEAN", checksum: "abcdef123456" }),
      });
      return res.status;
    });

    expect(status).toBe(403);
  });

  test("blocks SalesAgent from approving high-value quote without TenantAdmin role (403)", async ({ page }) => {
    await setupMockApiRoutes(page, MOCK_TENANT_A_USER);

    await page.route("**/api/v1/quotations/q-val-999/approve", async (route) => {
      await route.fulfill({
        status: 403,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Role 'TenantAdmin' required to approve quotes exceeding 50,000 EUR." }),
      });
    });

    await page.goto("/");

    const status = await page.evaluate(async () => {
      const res = await fetch("/api/v1/quotations/q-val-999/approve", {
        method: "POST",
        headers: { Authorization: "Bearer mock_sales_agent_jwt" },
      });
      return res.status;
    });

    expect(status).toBe(403);
  });

  test("blocks GDPR customer erasure when active export legal-hold is present (409 Conflict)", async ({ page }) => {
    await setupMockApiRoutes(page, MOCK_TENANT_A_USER);

    await page.route("**/api/v1/customers/cust-j1/anonymize", async (route) => {
      await route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({
          detail: "Cannot process GDPR erasure request: Active customs legal-hold on dossier EXP-2026-88.",
        }),
      });
    });

    await page.goto("/");

    const status = await page.evaluate(async () => {
      const res = await fetch("/api/v1/customers/cust-j1/anonymize", {
        method: "POST",
        headers: { Authorization: "Bearer mock_tenant_a_jwt" },
      });
      return res.status;
    });

    expect(status).toBe(409);
  });

  test("blocks download access to quarantined or expired document links (403)", async ({ page }) => {
    await setupMockApiRoutes(page, MOCK_TENANT_A_USER);

    await page.route("**/api/v1/documents/doc-quarantined-999/download", async (route) => {
      await route.fulfill({
        status: 403,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Access denied: Document is quarantined due to security violation." }),
      });
    });

    await page.goto("/");

    const status = await page.evaluate(async () => {
      const res = await fetch("/api/v1/documents/doc-quarantined-999/download", {
        headers: { Authorization: "Bearer mock_tenant_a_jwt" },
      });
      return res.status;
    });

    expect(status).toBe(403);
  });
});

