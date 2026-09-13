import React from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Car, MessageSquare, Users, FileText, CheckCircle2, ShieldCheck } from "lucide-react";
import { ToastContainer } from "../shared/components/feedback/ToastContainer";
import { QueryProvider } from "./providers/QueryProvider";

const OperationalShell: React.FC = () => {
  return (
    <div className="flex h-screen w-screen bg-crm-bg text-crm-text overflow-hidden font-sans">
      {/* Left Sidebar Navigation */}
      <aside className="w-16 flex-shrink-0 bg-crm-card border-r border-crm-border flex flex-col items-center py-4 space-y-6">
        <div className="p-2 bg-crm-primary/20 text-crm-primary rounded-lg">
          <Car className="w-6 h-6" />
        </div>
        <nav className="flex flex-col space-y-4 w-full items-center">
          <button className="p-2.5 text-crm-primary bg-crm-hover/50 rounded-lg transition-colors" title="Inbox Workspace">
            <MessageSquare className="w-5 h-5" />
          </button>
          <button className="p-2.5 text-crm-muted hover:text-crm-text hover:bg-crm-hover rounded-lg transition-colors" title="Customers">
            <Users className="w-5 h-5" />
          </button>
          <button className="p-2.5 text-crm-muted hover:text-crm-text hover:bg-crm-hover rounded-lg transition-colors" title="Quotes">
            <FileText className="w-5 h-5" />
          </button>
          <button className="p-2.5 text-crm-muted hover:text-crm-text hover:bg-crm-hover rounded-lg transition-colors" title="Documents & GDPR">
            <ShieldCheck className="w-5 h-5" />
          </button>
        </nav>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Top Operational Header */}
        <header className="h-12 bg-crm-card border-b border-crm-border flex items-center justify-between px-4 text-xs">
          <div className="flex items-center space-x-3">
            <span className="font-semibold text-crm-text">Car-Export-CRM</span>
            <span className="text-crm-border">|</span>
            <span className="text-crm-muted">Operational Workstation v1.0</span>
          </div>
          <div className="flex items-center space-x-3">
            <span className="crm-badge bg-crm-success/20 text-crm-success flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" /> System Operational
            </span>
            <span className="text-crm-muted">Tenant: Germany Export Hub</span>
          </div>
        </header>

        {/* Workspace Body */}
        <div className="flex-1 p-6 overflow-y-auto">
          <div className="max-w-4xl mx-auto space-y-6">
            <div className="bg-crm-card border border-crm-border rounded-lg p-6 space-y-4">
              <div className="flex items-center space-x-3">
                <MessageSquare className="w-6 h-6 text-crm-primary" />
                <h1 className="text-xl font-bold text-crm-text">Primary Operational Workspace Bootstrap</h1>
              </div>
              <p className="text-sm text-crm-muted leading-relaxed">
                Frontend architecture initialized with Vite, React 19, TypeScript strict mode, Tailwind CSS dark workstation palette, and Lucide iconography. High-density 3-pane WhatsApp inbox layout prepared for WS-17 workspace implementation.
              </p>
              <div className="grid grid-cols-3 gap-4 pt-2">
                <div className="bg-crm-bg p-3 border border-crm-border rounded text-xs space-y-1">
                  <div className="text-crm-muted font-medium">Server State Management</div>
                  <div className="font-mono text-crm-primary">TanStack Query v5</div>
                </div>
                <div className="bg-crm-bg p-3 border border-crm-border rounded text-xs space-y-1">
                  <div className="text-crm-muted font-medium">Design Policy</div>
                  <div className="font-mono text-crm-success">Zero AI Slop / Dense</div>
                </div>
                <div className="bg-crm-bg p-3 border border-crm-border rounded text-xs space-y-1">
                  <div className="text-crm-muted font-medium">REST API Client</div>
                  <div className="font-mono text-crm-ai">Axios + RFC 7807</div>
                </div>
              </div>
            </div>
          </div>
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
