import React from "react";
import { User, Phone, Mail, Globe, ShieldCheck, Car, FileText, ExternalLink, Layers } from "lucide-react";
import { CustomerContext, LeadContext } from "../types";

interface CustomerSidebarProps {
  customer?: CustomerContext;
  lead?: LeadContext;
}

export const CustomerSidebar: React.FC<CustomerSidebarProps> = ({ customer, lead }) => {
  if (!customer) {
    return (
      <aside className="w-[380px] flex-shrink-0 bg-slate-900 border-l border-slate-800 p-6 flex items-center justify-center text-xs text-slate-500 select-none">
        Sélectionnez une conversation pour afficher la fiche client & opportunité.
      </aside>
    );
  }

  const getStageColor = (stage?: string) => {
    switch (stage) {
      case "NEW":
        return "bg-blue-950 text-blue-400 border-blue-800";
      case "QUALIFIED":
        return "bg-amber-950 text-amber-400 border-amber-800";
      case "QUOTE_SENT":
        return "bg-purple-950 text-purple-400 border-purple-800";
      case "FCR_VERIFIED":
        return "bg-emerald-950 text-emerald-400 border-emerald-800";
      default:
        return "bg-slate-800 text-slate-300 border-slate-700";
    }
  };

  return (
    <aside className="w-[380px] flex-shrink-0 bg-slate-900 border-l border-slate-800 flex flex-col h-full overflow-y-auto select-none divide-y divide-slate-800/80">
      {/* Sidebar Header */}
      <div className="p-3 bg-slate-950/40 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <User className="w-4 h-4 text-blue-400" />
          <h3 className="text-xs font-semibold text-slate-100 uppercase tracking-wider">Fiche Client & Lead</h3>
        </div>
        <span className="text-[10px] font-mono text-slate-400">ID: {customer.id}</span>
      </div>

      {/* Customer Profile Section */}
      <div className="p-4 space-y-3">
        <div className="flex items-start justify-between">
          <div>
            <h4 className="text-sm font-bold text-slate-100">{customer.fullName}</h4>
            <div className="flex items-center gap-1 text-xs text-slate-400 mt-0.5 font-mono">
              <Phone className="w-3 h-3 text-slate-500" />
              <span>{customer.phoneE164}</span>
            </div>
          </div>
          {customer.fcrEligible ? (
            <span className="px-2 py-0.5 text-[10px] font-semibold bg-emerald-950 text-emerald-400 border border-emerald-800 rounded-full flex items-center gap-1 font-mono">
              <ShieldCheck className="w-3 h-3" />
              FCR Éligible
            </span>
          ) : (
            <span className="px-2 py-0.5 text-[10px] font-semibold bg-slate-800 text-slate-400 border border-slate-700 rounded-full font-mono">
              Standard (Non FCR)
            </span>
          )}
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs pt-1">
          <div className="bg-slate-950/60 p-2 rounded border border-slate-800/60">
            <span className="text-[10px] text-slate-500 block">Pays de Destination</span>
            <div className="flex items-center gap-1 text-slate-200 font-medium mt-0.5">
              <Globe className="w-3 h-3 text-slate-400" />
              <span>{customer.country}</span>
            </div>
          </div>

          <div className="bg-slate-950/60 p-2 rounded border border-slate-800/60">
            <span className="text-[10px] text-slate-500 block">E-mail</span>
            <div className="flex items-center gap-1 text-slate-200 font-medium mt-0.5 truncate">
              <Mail className="w-3 h-3 text-slate-400 flex-shrink-0" />
              <span className="truncate">{customer.email || "Non renseigné"}</span>
            </div>
          </div>
        </div>

        {customer.notes && (
          <div className="bg-slate-950/80 p-2.5 rounded border border-slate-800 text-xs text-slate-300">
            <span className="text-[10px] text-slate-500 block font-mono uppercase tracking-wider mb-1">Notes Client:</span>
            <p className="leading-relaxed text-slate-300 font-sans">{customer.notes}</p>
          </div>
        )}
      </div>

      {/* Vehicle Sourcing & Lead Stage Section */}
      <div className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <Car className="w-4 h-4 text-blue-400" />
            <h4 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">Sourcing Véhicule</h4>
          </div>
          {lead && (
            <span className={`px-2 py-0.5 text-[10px] font-mono font-bold rounded border ${getStageColor(lead.stage)}`}>
              {lead.stage}
            </span>
          )}
        </div>

        {lead ? (
          <div className="space-y-2">
            <div className="bg-slate-950/60 p-3 rounded border border-slate-800 space-y-1.5 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-slate-400 text-[11px]">Modèle Recherché:</span>
                <span className="font-semibold text-slate-100">{lead.targetVehicle || "Non spécifié"}</span>
              </div>

              <div className="flex items-center justify-between text-slate-400 text-[11px]">
                <span>Budget Estimé:</span>
                <span className="font-mono text-emerald-400 font-medium">
                  {lead.budgetMinEur ? `${lead.budgetMinEur.toLocaleString()} €` : "—"} -{" "}
                  {lead.budgetMaxEur ? `${lead.budgetMaxEur.toLocaleString()} €` : "—"}
                </span>
              </div>

              <div className="flex items-center justify-between text-slate-400 text-[11px]">
                <span>Conseiller Dédié:</span>
                <span className="text-slate-300">{lead.assignedAgentName || "Non attribué"}</span>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-xs text-slate-500 italic p-2 bg-slate-950/40 rounded">
            Aucun opportunité/lead actif associé.
          </div>
        )}
      </div>

      {/* Action Buttons Toolbar */}
      <div className="p-4 space-y-2 mt-auto">
        <button
          type="button"
          className="w-full py-2 px-3 bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs rounded transition-colors flex items-center justify-center gap-2 shadow-sm"
        >
          <FileText className="w-3.5 h-3.5" />
          Générer Devis FCR (Netto/Brutto)
        </button>

        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            className="py-1.5 px-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px] font-medium rounded border border-slate-700 transition-colors flex items-center justify-center gap-1"
          >
            <Layers className="w-3 h-3 text-slate-400" />
            Documents S3
          </button>
          <button
            type="button"
            className="py-1.5 px-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px] font-medium rounded border border-slate-700 transition-colors flex items-center justify-center gap-1"
          >
            <ExternalLink className="w-3 h-3 text-slate-400" />
            Fiche Client
          </button>
        </div>
      </div>
    </aside>
  );
};
