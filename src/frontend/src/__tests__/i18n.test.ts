import { describe, it, expect } from "vitest";
import i18n from "../shared/i18n";

describe("i18n & RTL Layout Infrastructure", () => {
  it("initializes default language as French ('fr')", () => {
    expect(i18n.language).toBe("fr");
    expect(i18n.t("app.title")).toBe("Car-Export-CRM");
    expect(i18n.t("nav.inbox")).toBe("Boîte de Réception");
  });

  it("switches language to English ('en')", async () => {
    await i18n.changeLanguage("en");
    expect(i18n.language).toBe("en");
    expect(i18n.t("nav.inbox")).toBe("Inbox Workspace");
  });

  it("switches language to Arabic ('ar') and updates document dir attribute to 'rtl'", async () => {
    await i18n.changeLanguage("ar");
    expect(i18n.language).toBe("ar");
    expect(document.documentElement.dir).toBe("rtl");
    expect(document.documentElement.lang).toBe("ar");
  });
});
