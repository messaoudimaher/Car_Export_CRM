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
    const data = [
      {
        id: "th_01h9x8a1",
        customerId: "cust_991",
        customerName: "Mohamed Ben Ali",
        customerPhone: "+216 98 123 456",
        channel: "WHATSAPP",
        status: "ASSIGNED",
        unreadCount: 2,
        lastMessageSnippet: "Bonjour, je cherche une BMW X5 2022 éligible FCR avec TVA déductible.",
        lastActivityAt: "2026-09-13T17:42:00Z",
        assignedAgentId: "agent_01",
        assignedAgentName: "Sami Khedira",
        customer: {
          id: "cust_991",
          fullName: "Mohamed Ben Ali",
          phoneE164: "+21698123456",
          email: "m.benali@gmail.com",
          country: "Tunisia",
          fcrEligible: true,
          notes: "Client sérieux. Privilégie SUV allemand récent.",
          createdAt: "2026-08-10T10:00:00Z",
        },
        lead: {
          id: "lead_501",
          customerId: "cust_991",
          stage: "QUALIFIED",
          targetVehicle: "BMW X5 xDrive30d M Sport (2022-2023)",
          budgetMinEur: 45000,
          budgetMaxEur: 55000,
          assignedAgentName: "Sami Khedira",
          updatedAt: "2026-09-13T16:30:00Z",
        },
        activeAiUnderstanding: {
          id: "ai_und_901",
          threadId: "th_01h9x8a1",
          messageId: "msg_103",
          extractedVehicleModel: "BMW X5 xDrive30d",
          extractedYearMin: 2022,
          extractedYearMax: 2023,
          extractedBudgetMinEur: 45000,
          extractedBudgetMaxEur: 55000,
          extractedFcrEligible: true,
          confidenceScore: 0.94,
          status: "PROVISIONAL",
          createdAt: "2026-09-13T17:42:05Z",
        },
        activeAiSuggestion: {
          id: "ai_sug_901",
          threadId: "th_01h9x8a1",
          messageId: "msg_103",
          suggestedText: "Bonjour M. Ben Ali, nous pouvons vous établir immédiatement un devis FCR avec TVA déductible (Netto) pour la BMW X5 2022.",
          confidenceScore: 0.91,
          status: "PROVISIONAL",
          createdAt: "2026-09-13T17:42:10Z",
        },
      },
    ];
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(data) });
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
          id: "doc_001",
          filename: "Carte_Grise_BMW_X5_WBA123.pdf",
          category: "CARTE_GRISE",
          mimeType: "application/pdf",
          sizeBytes: 2450000,
          sha256Checksum: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
          scanStatus: "PASSED",
          uploadedBy: "Mohamed Ben Ali",
          createdAt: "2026-09-13T10:00:00Z",
        },
        {
          id: "doc_003",
          filename: "Passeport_Scan_Karim_Mansour.pdf",
          category: "PASSPORT",
          mimeType: "application/pdf",
          sizeBytes: 3100000,
          sha256Checksum: "9b7852b855e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991",
          scanStatus: "PENDING_SCAN",
          uploadedBy: "Karim Mansour",
          createdAt: "2026-09-13T16:50:00Z",
        },
        {
          id: "doc_004",
          filename: "Facture_Douanier_Suspecte.exe.pdf",
          category: "CUSTOMS_FORM",
          mimeType: "application/pdf",
          sizeBytes: 4200000,
          sha256Checksum: "7a123b456c789d012e345f6789a01b234c567d890e123f456a789b012c345d67",
          scanStatus: "QUARANTINED",
          uploadedBy: "Unknown Transporter",
          createdAt: "2026-09-13T17:30:00Z",
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
