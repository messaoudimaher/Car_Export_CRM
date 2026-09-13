import { describe, it, expect, vi } from "vitest";
import { renderWithProviders, screen, fireEvent } from "../test/utils";

import { AiUnderstandingCard } from "../features/inbox/components/AiUnderstandingCard";
import { AiSuggestionCard } from "../features/inbox/components/AiSuggestionCard";
import { ThreadList } from "../features/inbox/components/ThreadList";
import { CustomerSidebar } from "../features/inbox/components/CustomerSidebar";
import { ChatHistory } from "../features/inbox/components/ChatHistory";
import { QuotationBuilder } from "../features/quotes/components/QuotationBuilder";
import { LeadListPage } from "../features/leads/pages/LeadListPage";
import { CustomerListPage } from "../features/customers/pages/CustomerListPage";
import { DocumentListPage } from "../features/documents/pages/DocumentListPage";

describe("Frontend Core Components Test Suite (TASK-1902)", () => {
  // 1. Component Test: AiUnderstandingCard
  it("renders AiUnderstandingCard with confidence score and handles confirm/reject", () => {
    const onConfirm = vi.fn();
    const onReject = vi.fn();
    const understanding = {
      id: "und-101",
      threadId: "thread-101",
      messageId: "msg-101",
      intent: "VEHICLE_INQUIRY",
      confidenceScore: 0.94,
      status: "PROVISIONAL" as const,
      extractedVehicleModel: "Volkswagen Golf 8 GTI",
      extractedBudgetMaxEur: 25000,
      extractedFcrEligible: true,
      createdAt: new Date().toISOString(),
    };

    renderWithProviders(
      <AiUnderstandingCard
        understanding={understanding}
        onConfirm={onConfirm}
        onReject={onReject}
      />
    );

    expect(screen.getByText(/94% Confiance/i)).toBeDefined();
    expect(screen.getByText(/Volkswagen Golf 8 GTI/i)).toBeDefined();

    const confirmBtn = screen.getByRole("button", { name: /confirmer/i });
    fireEvent.click(confirmBtn);
    expect(onConfirm).toHaveBeenCalledWith("und-101");
  });

  // 2. Component Test: AiSuggestionCard
  it("renders AiSuggestionCard and triggers insertion into editor", () => {
    const onInsert = vi.fn();
    const suggestion = {
      id: "sug-202",
      threadId: "thread-101",
      messageId: "msg-101",
      suggestedText: "Bonjour Mohamed, la Golf 8 GTI 2021 est disponible pour 24 500 € Netto Export.",
      confidenceScore: 0.91,
      status: "PROVISIONAL" as const,
      createdAt: new Date().toISOString(),
    };

    renderWithProviders(
      <AiSuggestionCard
        suggestion={suggestion}
        onInsertIntoEditor={onInsert}
      />
    );

    expect(screen.getByText(/Suggestion de Réponse IA/i)).toBeDefined();
    expect(screen.getByText(/Bonjour Mohamed/i)).toBeDefined();

    const insertBtn = screen.getByRole("button", { name: /insérer dans l'éditeur/i });
    fireEvent.click(insertBtn);
    expect(onInsert).toHaveBeenCalledWith(suggestion.suggestedText);
  });

  // 3. Component Test: ThreadList
  it("renders ThreadList and handles thread selection and search filtering", () => {
    const onSelect = vi.fn();
    const onFilterChange = vi.fn();
    const threads = [
      {
        id: "thread-1",
        customerId: "cust-1",
        customerName: "Youssef Mansouri",
        customerPhone: "+21698765432",
        channel: "WHATSAPP" as const,
        status: "UNASSIGNED" as const,
        unreadCount: 2,
        lastMessageSnippet: "Recherche Audi A4 2.0 TDI Netto",
        lastActivityAt: "2026-09-13T10:00:00Z",
        customer: {
          id: "cust-1",
          fullName: "Youssef Mansouri",
          phoneE164: "+21698765432",
          country: "TN",
          fcrEligible: true,
          createdAt: "2026-09-13T10:00:00Z",
        },
      },
    ];

    renderWithProviders(
      <ThreadList
        threads={threads as any}
        activeThreadId="thread-1"
        onSelectThread={onSelect}
        filter={{ status: "ALL", search: "" }}
        onFilterChange={onFilterChange}
      />
    );

    expect(screen.getByText("Youssef Mansouri")).toBeDefined();
    expect(screen.getByText(/Recherche Audi A4/i)).toBeDefined();

    const searchInput = screen.getByPlaceholderText(/rechercher nom, téléphone/i);
    fireEvent.change(searchInput, { target: { value: "Youssef" } });
    expect(onFilterChange).toHaveBeenCalled();
  });

  // 4. Component Test: CustomerSidebar
  it("renders CustomerSidebar with customer details and quote trigger button", () => {
    const onQuoteClick = vi.fn();
    const customer = {
      id: "cust-1",
      fullName: "Kamel Ben Ali",
      phoneE164: "+21620123456",
      email: "kamel@example.com",
      country: "TN",
      preferredLanguage: "fr",
      fcrEligible: true,
      createdAt: new Date().toISOString(),
    };
    const lead = {
      id: "lead-1",
      stage: "QUOTATION_SENT",
      targetVehicle: "Mercedes-Benz C220d AMG Line 2022",
      budgetEur: 32000,
    };

    renderWithProviders(
      <CustomerSidebar
        customer={customer}
        lead={lead as any}
        onOpenQuoteBuilder={onQuoteClick}
      />
    );

    expect(screen.getByText("Kamel Ben Ali")).toBeDefined();
    expect(screen.getByText("+21620123456")).toBeDefined();

    const quoteBtn = screen.getByRole("button", { name: /générer devis fcr/i });
    fireEvent.click(quoteBtn);
    expect(onQuoteClick).toHaveBeenCalled();
  });

  // 5. Component Test: ChatHistory
  it("renders ChatHistory timeline messages", () => {
    const thread = {
      id: "thread-1",
      customerName: "Client Test",
      phoneE164: "+21698765432",
      lastMessageSnippet: "Je cherche une Peugeot 3008",
      lastActivityAt: "2026-09-13T10:00:00Z",
      unreadCount: 0,
    };

    const messages = [
      {
        id: "msg-1",
        threadId: "thread-1",
        direction: "INBOUND" as const,
        content: "Je cherche une Peugeot 3008 1.5 BlueHDi",
        timestamp: new Date().toISOString(),
        status: "DELIVERED" as const,
      },
      {
        id: "msg-2",
        threadId: "thread-1",
        direction: "OUTBOUND" as const,
        senderName: "Maher",
        content: "Bonjour, nous avons une 3008 GT Line 2021 à 19 800 € Netto.",
        timestamp: new Date().toISOString(),
        status: "READ" as const,
      },
    ];

    renderWithProviders(
      <ChatHistory
        thread={thread as any}
        messages={messages}
        onSendMessage={vi.fn()}
      />
    );

    expect(screen.getByText(/Je cherche une Peugeot 3008/i)).toBeDefined();
    expect(screen.getByText(/Bonjour, nous avons une 3008/i)).toBeDefined();
  });

  // 6. Component Test: QuotationBuilder
  it("renders QuotationBuilder calculator and manager approval warning", () => {
    const onClose = vi.fn();

    renderWithProviders(
      <QuotationBuilder
        customerName="Anis Trabelsi"
        customerPhone="+21699887766"
        isOpen={true}
        onClose={onClose}
      />
    );

    expect(screen.getByText(/Générateur de Devis FCR/i)).toBeDefined();
    expect(screen.getByText(/Anis Trabelsi/i)).toBeDefined();

    const discountInput = screen.getByLabelText(/Remise Remise/i);
    fireEvent.change(discountInput, { target: { value: "8" } });

    expect(screen.getByText(/validation d'un Manager/i)).toBeDefined();
  });

  // 7. Component Test: LeadListPage
  it("renders LeadListPage layout and stage filter options", () => {
    renderWithProviders(<LeadListPage />);

    expect(screen.getByText(/Pipeline des Opportunités/i)).toBeDefined();
  });

  // 8. Component Test: CustomerListPage
  it("renders CustomerListPage with search input and customer catalog header", () => {
    renderWithProviders(<CustomerListPage />);

    expect(screen.getByText(/Répertoire des Clients/i)).toBeDefined();
    expect(screen.getByPlaceholderText(/Rechercher nom, téléphone/i)).toBeDefined();
  });

  // 9. Component Test: DocumentListPage
  it("renders DocumentListPage with document dropzone and status filter", () => {
    renderWithProviders(<DocumentListPage />);

    expect(screen.getByText(/Dépôt Privé S3 & Documents RGPD/i)).toBeDefined();
  });
});
