import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { AiUnderstandingCard } from "../features/inbox/components/AiUnderstandingCard";
import { AiSuggestionCard } from "../features/inbox/components/AiSuggestionCard";
import { AiUnderstanding, AiSuggestion } from "../features/inbox/types";

const mockUnderstanding: AiUnderstanding = {
  id: "und_1",
  threadId: "th_1",
  messageId: "msg_1",
  extractedVehicleModel: "Mercedes-Benz GLE Coupe",
  extractedYearMin: 2022,
  extractedYearMax: 2023,
  extractedBudgetMinEur: 55000,
  extractedBudgetMaxEur: 70000,
  extractedFcrEligible: true,
  confidenceScore: 0.95,
  status: "PROVISIONAL",
  createdAt: new Date().toISOString(),
};

const mockSuggestion: AiSuggestion = {
  id: "sug_1",
  threadId: "th_1",
  messageId: "msg_1",
  suggestedText: "Bonjour M. Mansour, voici notre sélection de Mercedes GLE Coupe éligibles FCR Netto.",
  reasoningSnippet: "Recherche GLE Coupe confirmée.",
  confidenceScore: 0.92,
  status: "PROVISIONAL",
  createdAt: new Date().toISOString(),
};

describe("AI HITL Visual Hierarchy Components (INV-003, ADR 0012)", () => {
  it("renders AiUnderstandingCard with Indigo provisional badge and triggers onConfirm", () => {
    const onConfirm = vi.fn();
    const onReject = vi.fn();

    render(
      <AiUnderstandingCard
        understanding={mockUnderstanding}
        onConfirm={onConfirm}
        onReject={onReject}
      />
    );

    expect(screen.getByText("Extraction IA — Provisoire (Unconfirmed)")).toBeDefined();
    expect(screen.getByText("Mercedes-Benz GLE Coupe")).toBeDefined();
    expect(screen.getByText("95% Confiance")).toBeDefined();

    const confirmBtn = screen.getByText("Confirmer & Appliquer au Lead");
    fireEvent.click(confirmBtn);
    expect(onConfirm).toHaveBeenCalledWith("und_1");
  });

  it("renders AiSuggestionCard with Amber provisional badge and triggers onInsertIntoEditor & onApproveAndSend", () => {
    const onApprove = vi.fn();
    const onInsert = vi.fn();
    const onReject = vi.fn();

    render(
      <AiSuggestionCard
        suggestion={mockSuggestion}
        onApproveAndSend={onApprove}
        onInsertIntoEditor={onInsert}
        onReject={onReject}
      />
    );

    expect(screen.getByText("Suggestion de Réponse IA — Non Envoyée")).toBeDefined();
    expect(screen.getByText("Bonjour M. Mansour, voici notre sélection de Mercedes GLE Coupe éligibles FCR Netto.")).toBeDefined();
    expect(screen.getByText("92% Confiance")).toBeDefined();

    const insertBtn = screen.getByText("Insérer dans l'Éditeur");
    fireEvent.click(insertBtn);
    expect(onInsert).toHaveBeenCalledWith("Bonjour M. Mansour, voici notre sélection de Mercedes GLE Coupe éligibles FCR Netto.");

    const approveBtn = screen.getByText("Approuver & Envoyer WhatsApp");
    fireEvent.click(approveBtn);
    expect(onApprove).toHaveBeenCalledWith(mockSuggestion);
  });
});
