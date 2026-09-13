import React from "react";
import { BrowserRouter, Route, Routes, NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Car, MessageSquare, Users, ShieldCheck, CheckCircle2, Layers } from "lucide-react";
import { ToastContainer } from "../shared/components/feedback/ToastContainer";
import { LanguageSelector } from "../shared/components/ui/LanguageSelector";
import { QueryProvider } from "./providers/QueryProvider";
import { InboxWorkspace } from "../features/inbox/components/InboxWorkspace";
import { CustomerListPage } from "../features/customers/pages/CustomerListPage";
import { LeadListPage } from "../features/leads/pages/LeadListPage";
import { DocumentListPage } from "../features/documents/pages/DocumentListPage";
import "../shared/i18n";

const OperationalShell: React.FC = () => {
  const { t } = useTranslation();

  return (
    <div className="flex h-screen w-screen bg-crm-bg text-crm-text overflow-hidden font-sans">
      {/* Left Sidebar Navigation */}
      <aside className="w-16 flex-shrink-0 bg-crm-card border-r border-crm-border flex flex-col items-center py-4 space-y-6">
        <div className="p-2 bg-crm-primary/20 text-crm-primary rounded-lg">
          <Car className="w-6 h-6" />
        </div>
        <nav className="flex flex-col space-y-4 w-full items-center">
          <NavLink
            to="/"
            className={({ isActive }) =>
              `p-2.5 rounded-lg transition-colors ${
                isActive ? "text-crm-primary bg-crm-hover/50" : "text-crm-muted hover:text-crm-text hover:bg-crm-hover"
              }`
            }
            title={t("nav.inbox")}
          >
            <MessageSquare className="w-5 h-5" />
          </NavLink>

          <NavLink
            to="/customers"
            className={({ isActive }) =>
              `p-2.5 rounded-lg transition-colors ${
                isActive ? "text-crm-primary bg-crm-hover/50" : "text-crm-muted hover:text-crm-text hover:bg-crm-hover"
              }`
            }
            title={t("nav.customers")}
          >
            <Users className="w-5 h-5" />
          </NavLink>

          <NavLink
            to="/leads"
            className={({ isActive }) =>
              `p-2.5 rounded-lg transition-colors ${
                isActive ? "text-crm-primary bg-crm-hover/50" : "text-crm-muted hover:text-crm-text hover:bg-crm-hover"
              }`
            }
            title="Pipeline Opportunités"
          >
            <Layers className="w-5 h-5" />
          </NavLink>

          <NavLink
            to="/documents"
            className={({ isActive }) =>
              `p-2.5 rounded-lg transition-colors ${
                isActive ? "text-crm-primary bg-crm-hover/50" : "text-crm-muted hover:text-crm-text hover:bg-crm-hover"
              }`
            }
            title={t("nav.documents")}
          >
            <ShieldCheck className="w-5 h-5" />
          </NavLink>
        </nav>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Top Operational Header */}
        <header className="h-12 bg-crm-card border-b border-crm-border flex items-center justify-between px-4 text-xs">
          <div className="flex items-center space-x-3 rtl:space-x-reverse">
            <span className="font-semibold text-crm-text">{t("app.title")}</span>
            <span className="text-crm-border">|</span>
            <span className="text-crm-muted">{t("app.subtitle")}</span>
          </div>
          <div className="flex items-center space-x-3 rtl:space-x-reverse">
            <span className="crm-badge bg-crm-success/20 text-crm-success flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" /> {t("app.systemOperational")}
            </span>
            <span className="text-crm-muted">{t("app.tenant")}</span>
            <LanguageSelector />
          </div>
        </header>

        {/* Workspace Body Routes */}
        <div className="flex-1 flex overflow-hidden">
          <Routes>
            <Route path="/" element={<InboxWorkspace />} />
            <Route path="/customers" element={<CustomerListPage />} />
            <Route path="/leads" element={<LeadListPage />} />
            <Route path="/documents" element={<DocumentListPage />} />
          </Routes>
        </div>
      </main>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <QueryProvider>
      <BrowserRouter>
        <Routes>
          <Route path="*" element={<OperationalShell />} />
        </Routes>
        <ToastContainer />
      </BrowserRouter>
    </QueryProvider>
  );
};
