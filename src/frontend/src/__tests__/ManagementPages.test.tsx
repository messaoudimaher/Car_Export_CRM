import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CustomerListPage } from "../features/customers/pages/CustomerListPage";
import { LeadListPage } from "../features/leads/pages/LeadListPage";
import { DocumentListPage } from "../features/documents/pages/DocumentListPage";

describe("Customer, Lead & Document Management Views (TASK-1705)", () => {
  it("renders CustomerListPage directory table with FCR filter buttons", () => {
    render(<CustomerListPage />);

    expect(screen.getByText("Répertoire des Clients")).toBeDefined();
    expect(screen.getByText("Mohamed Ben Ali")).toBeDefined();
    expect(screen.getByText("Karim Mansour")).toBeDefined();

    const fcrFilterBtn = screen.getByText("FCR Éligibles");
    fireEvent.click(fcrFilterBtn);

    expect(screen.getAllByText("FCR TRE Éligible").length).toBeGreaterThan(0);
  });

  it("renders LeadListPage pipeline table with stage filters", () => {
    render(<LeadListPage />);

    expect(screen.getByText("Pipeline des Opportunités (Leads)")).toBeDefined();
    expect(screen.getByText("BMW X5 xDrive30d M Sport (2022-2023)")).toBeDefined();
    expect(screen.getByText("QUALIFIED")).toBeDefined();
  });

  it("renders DocumentListPage repository with SHA-256 scan status pills", () => {
    render(<DocumentListPage />);

    expect(screen.getByText("Dépôt Privé S3 & Documents RGPD")).toBeDefined();
    expect(screen.getByText("Carte_Grise_BMW_X5_WBA123.pdf")).toBeDefined();
    expect(screen.getAllByText("PASSED (SHA-256 Valid)").length).toBeGreaterThan(0);
  });
});
