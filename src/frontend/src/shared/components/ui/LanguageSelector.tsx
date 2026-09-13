import React from "react";
import { useTranslation } from "react-i18next";
import { Globe } from "lucide-react";
import { SUPPORTED_LANGUAGES, SupportedLanguage } from "../../i18n";

export const LanguageSelector: React.FC = () => {
  const { i18n } = useTranslation();

  const handleLanguageChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newLang = e.target.value as SupportedLanguage;
    i18n.changeLanguage(newLang);
  };

  return (
    <div className="flex items-center space-x-1.5 bg-crm-bg border border-crm-border rounded px-2 py-1 text-xs">
      <Globe className="w-3.5 h-3.5 text-crm-muted" />
      <select
        value={i18n.language}
        onChange={handleLanguageChange}
        className="bg-transparent text-crm-text focus:outline-none cursor-pointer font-medium"
        aria-label="Select Application UI Language"
      >
        {SUPPORTED_LANGUAGES.map((lang) => (
          <option key={lang.code} value={lang.code} className="bg-crm-card text-crm-text">
            {lang.name}
          </option>
        ))}
      </select>
    </div>
  );
};
