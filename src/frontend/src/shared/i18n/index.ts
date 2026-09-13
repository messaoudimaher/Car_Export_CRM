import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import fr from "./locales/fr.json";
import en from "./locales/en.json";
import ar from "./locales/ar.json";

export const SUPPORTED_LANGUAGES = [
  { code: "fr", name: "Français", dir: "ltr" },
  { code: "en", name: "English", dir: "ltr" },
  { code: "ar", name: "العربية", dir: "rtl" },
] as const;

export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number]["code"];

const updateDocumentDirection = (lang: string) => {
  const isRtl = lang === "ar";
  document.documentElement.dir = isRtl ? "rtl" : "ltr";
  document.documentElement.lang = lang;
};

// Initialize i18next instance
i18n.use(initReactI18next).init({
  resources: {
    fr: { translation: fr },
    en: { translation: en },
    ar: { translation: ar },
  },
  lng: "fr", // Default UI language
  fallbackLng: "fr",
  interpolation: {
    escapeValue: false, // React already escapes values safely
  },
});

// Update root HTML element direction on language change
i18n.on("languageChanged", (lng: string) => {
  updateDocumentDirection(lng);
});

// Initial direction setup
updateDocumentDirection(i18n.language || "fr");

export default i18n;
