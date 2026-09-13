import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ThreadList } from "../features/inbox/components/ThreadList";
import { CustomerSidebar } from "../features/inbox/components/CustomerSidebar";
import { ConversationThread } from "../features/inbox/types";

const mockThread: ConversationThread = {
  id: "th_1",
  customerId: "c_1",
  customerName: "Sami Mansour",
  customerPhone: "+21698765432",
  channel: "WHATSAPP",
  status: "ASSIGNED",
  unreadCount: 3,
  lastMessageSnippet: "Demande devis FCR pour Porsche Macan",
  lastActivityAt: new Date().toISOString(),
  customer: {
    id: "c_1",
    fullName: "Sami Mansour",
    phoneE164: "+21698765432",
    country: "Tunisia",
    fcrEligible: true,
    createdAt: new Date().toISOString(),
  },
  lead: {
    id: "l_1",
    customerId: "c_1",
    stage: "QUALIFIED",
    targetVehicle: "Porsche Macan GTS 2023",
    budgetMinEur: 60000,
    budgetMaxEur: 75000,
    updatedAt: new Date().toISOString(),
  },
};

describe("Inbox Operational Workspace Components", () => {
  it("renders ThreadList with thread item and unread badge", () => {
    const onSelect = vi.fn();
    const onFilter = vi.fn();

    render(
      <ThreadList
        threads={[mockThread]}
        activeThreadId="th_1"
        onSelectThread={onSelect}
        filter={{ status: "ALL" }}
        onFilterChange={onFilter}
      />
    );

    expect(screen.getByText("Sami Mansour")).toBeDefined();
    expect(screen.getByText("Demande devis FCR pour Porsche Macan")).toBeDefined();
    expect(screen.getByText("3")).toBeDefined(); // Unread badge
    expect(screen.getByText("FCR")).toBeDefined(); // FCR badge
  });

  it("renders CustomerSidebar with customer profile and vehicle lead details", () => {
    render(<CustomerSidebar customer={mockThread.customer} lead={mockThread.lead} />);

    expect(screen.getByText("Sami Mansour")).toBeDefined();
    expect(screen.getByText("+21698765432")).toBeDefined();
    expect(screen.getByText("FCR Éligible")).toBeDefined();
    expect(screen.getByText("Porsche Macan GTS 2023")).toBeDefined();
    expect(screen.getByText("QUALIFIED")).toBeDefined();
  });
});
