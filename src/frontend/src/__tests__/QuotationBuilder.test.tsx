import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QuotationBuilder } from "../features/quotes/components/QuotationBuilder";

describe("FCR Quotation Builder UI & PDF Preview (BR-005, BR-006)", () => {
  it("calculates Netto VAT 0% price breakdown correctly for Netto Export", () => {
    const onClose = vi.fn();
    const onSendQuote = vi.fn();

    render(
      <QuotationBuilder
        customerName="Mohamed Ben Ali"
        customerPhone="+21698123456"
        isOpen={true}
        onClose={onClose}
        onSendQuoteToChat={onSendQuote}
      />
    );

    expect(screen.getByText("Générateur de Devis FCR")).toBeDefined();
    expect(screen.getByText("Client: Mohamed Ben Ali (+21698123456)")).toBeDefined();

    // 45,000 € vehicle + 1,200 € transport + 800 € service = 47,000 €
    expect(screen.getByText(/47.*000/)).toBeDefined();
    expect(screen.getByText("Notice Exonération Douane FCR TRE:")).toBeDefined();
  });

  it("opens PDF preview modal when clicking Générer & Aperçu PDF", () => {
    render(
      <QuotationBuilder
        customerName="Mohamed Ben Ali"
        customerPhone="+21698123456"
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    const generatePdfBtn = screen.getByText("Générer & Aperçu PDF Pre-signed");
    fireEvent.click(generatePdfBtn);

    expect(screen.getByText("Aperçu PDF Devis Officiel FCR (Pre-signed S3)")).toBeDefined();
    expect(screen.getByText("Attacher & Envoyer sur WhatsApp")).toBeDefined();
  });
});
