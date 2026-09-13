import { Page, expect } from "@playwright/test";

/**
 * Playwright E2E Helper Fixtures & Utilities (TASK-1903).
 */

export interface TestUser {
  id: string;
  email: string;
  fullName: string;
  role: "SuperAdmin" | "TenantAdmin" | "SalesAgent" | "LogisticsAgent";
  tenantId: string;
}

export const MOCK_TENANT_A_USER: TestUser = {
  id: "user-a-101",
  email: "sales_a@autoexport.com",
  fullName: "Maher Sales Agent",
  role: "SalesAgent",
  tenantId: "tenant-a-1111",
};

export const MOCK_LOGISTICS_USER: TestUser = {
  id: "user-b-202",
  email: "logistics@autoexport.com",
  fullName: "Sami Logistics Agent",
  role: "LogisticsAgent",
  tenantId: "tenant-a-1111",
};

export const MOCK_TENANT_B_USER: TestUser = {
  id: "user-c-303",
  email: "agent@competitor.com",
  fullName: "Competitor Agent",
  role: "SalesAgent",
  tenantId: "tenant-b-2222",
};

/**
 * Mock API routes for local offline E2E test execution.
 */
export async function setupMockApiRoutes(page: Page, user: TestUser = MOCK_TENANT_A_USER) {
  // Mock Health check endpoint
  await page.route("**/api/v1/health**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok", environment: "test" }),
    });
  });

  // Mock Conversations API list
  await page.route("**/api/v1/conversations**", async (route) => {
    const json = {
      success: true,
      data: [
        {
          id: "thread-j1",
          customerId: "cust-j1",
          customerName: "Mohamed Ben Ali",
          customerPhone: "+21698765432",
          channel: "WHATSAPP",
          status: "UNASSIGNED",
          unreadCount: 1,
          lastMessageSnippet: "Bonjour, je cherche une Golf 8 TDI 2021",
          lastActivityAt: new Date().toISOString(),
          customer: {
            id: "cust-j1",
            fullName: "Mohamed Ben Ali",
            phoneE164: "+21698765432",
            country: "TN",
            fcrEligible: true,
            createdAt: new Date().toISOString(),
          },
          activeAiUnderstanding: {
            id: "und-j1",
            threadId: "thread-j1",
            messageId: "msg-j1",
            extractedVehicleModel: "Volkswagen Golf 8 TDI",
            extractedBudgetMaxEur: 18000,
            extractedFcrEligible: true,
            confidenceScore: 0.94,
            status: "PROVISIONAL",
            createdAt: new Date().toISOString(),
          },
          activeAiSuggestion: {
            id: "sug-j1",
            threadId: "thread-j1",
            messageId: "msg-j1",
            suggestedText: "Bonjour Mohamed, nous avons plusieurs Golf 8 TDI disponibles à partir de 17 500 € HT.",
            confidenceScore: 0.92,
            status: "PROVISIONAL",
            createdAt: new Date().toISOString(),
          },
        },
      ],
      meta: { limit: 25, has_next: false, total: 1 },
    };
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(json) });
  });

  // Mock Customer list API
  await page.route("**/api/v1/customers**", async (route) => {
    const json = {
      success: true,
      data: [
        {
          id: "cust-j1",
          full_name: "Mohamed Ben Ali",
          phone_e164: "+21698765432",
          email: "mohamed@example.com",
          preferred_language: "fr",
          fcr_eligible: true,
        },
      ],
      meta: { total: 1 },
    };
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(json) });
  });

  // Mock Leads API
  await page.route("**/api/v1/leads**", async (route) => {
    const json = {
      success: true,
      data: [
        {
          id: "lead-j1",
          customerId: "cust-j1",
          stage: "QUALIFIED",
          targetVehicle: "Volkswagen Golf 8 TDI (2021)",
          budgetMaxEur: 18000,
          updatedAt: new Date().toISOString(),
        },
      ],
    };
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(json) });
  });

  // Mock Documents API
  await page.route("**/api/v1/documents**", async (route) => {
    const json = {
      success: true,
      data: [
        {
          id: "doc-j6",
          filename: "carte_grise_golf8.pdf",
          category: "CARTE_GRISE",
          fileSizeBytes: 2048500,
          scanStatus: "CLEAN",
          uploadedBy: "Sales Agent",
          downloadUrl: "https://s3.amazonaws.com/private-bucket/carte_grise.pdf?X-Amz-Expires=900",
        },
      ],
    };
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(json) });
  });

  // Mock Authentication headers into local session
  await page.addInitScript((userObj) => {
    localStorage.setItem("auth_token", "mock_jwt_token_header_payload");
    localStorage.setItem("user_profile", JSON.stringify(userObj));
  }, user);
}
