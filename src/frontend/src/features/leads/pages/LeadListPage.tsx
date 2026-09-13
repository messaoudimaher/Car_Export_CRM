import React, { useState } from "react";
import { Layers, Search, Car, UserCheck, Plus } from "lucide-react";
import { LeadContext } from "../../inbox/types";

const MOCK_LEADS: (LeadContext & { customerName: string })[] = [
  {
    id: "lead_501",
    customerId: "cust_991",
    customerName: "Mohamed Ben Ali",
    stage: "QUALIFIED",
    targetVehicle: "BMW X5 xDrive30d M Sport (2022-2023)",
    budgetMinEur: 45000,
    budgetMaxEur: 55000,
    assignedAgentName: "Sami Khedira",
    updatedAt: "2026-09-13T16:30:00Z",
  },
  {
    id: "lead_502",
    customerId: "cust_992",
    customerName: "Youssef Trabelsi",
    stage: "NEW",
    targetVehicle: "Mercedes-Benz C200 AMG Line",
    budgetMinEur: 30000,
    budgetMaxEur: 38000,
    assignedAgentName: "Non attribué",
    updatedAt: "2026-09-13T16:15:00Z",
  },
  {
    id: "lead_503",
    customerId: "cust_993",
    customerName: "Karim Mansour",
    stage: "QUOTE_SENT",
    targetVehicle: "Audi Q5 40 TDI S-Line 2023",
    budgetMinEur: 40000,
    budgetMaxEur: 48000,
    assignedAgentName: "Sami Khedira",
    updatedAt: "2026-09-12T11:00:00Z",
  },
];

export const LeadListPage: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState("");
  const [stageFilter, setStageFilter] = useState<string>("ALL");

  const filteredLeads = MOCK_LEADS.filter((l) => {
    const matchesSearch =
      l.customerName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (l.targetVehicle && l.targetVehicle.toLowerCase().includes(searchQuery.toLowerCase()));

    if (stageFilter !== "ALL") return matchesSearch && l.stage === stageFilter;
    return matchesSearch;
  });

  const getStageColor = (stage: string) => {
    switch (stage) {
      case "NEW":
        return "bg-blue-950 text-blue-400 border-blue-800";
      case "QUALIFIED":
        return "bg-amber-950 text-amber-400 border-amber-800";
      case "QUOTE_SENT":
        return "bg-purple-950 text-purple-400 border-purple-800";
      case "FCR_VERIFIED":
        return "bg-emerald-950 text-emerald-400 border-emerald-800";
      case "WON":
        return "bg-emerald-900 text-emerald-200 border-emerald-700";
      default:
        return "bg-slate-800 text-slate-300 border-slate-700";
    }
  };

  return (
    <div className="flex-1 flex flex-col bg-slate-950 p-6 overflow-y-auto font-sans text-slate-100 select-none">
      {/* Header Bar */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="flex items-center gap-2">
            <Layers className="w-6 h-6 text-amber-400" />
            <h1 className="text-xl font-bold text-slate-100">Pipeline des Opportunités (Leads)</h1>
          </div>
          <p className="text-xs text-slate-400 mt-1 font-mono">
            Suivi des demandes d'achat et devis d'exportation Allemagne ➔ Tunisie
          </p>
        </div>

        <button
          type="button"
          className="px-3.5 py-2 text-xs bg-amber-600 hover:bg-amber-500 text-white font-medium rounded-lg transition-colors flex items-center gap-1.5 shadow-sm"
        >
          <Plus className="w-4 h-4" />
          Nouveau Lead
        </button>
      </div>

      {/* Filter & Search Toolbar */}
      <div className="bg-slate-900 p-4 rounded-xl border border-slate-800 mb-6 flex items-center justify-between gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
          <input
            type="text"
            placeholder="Rechercher nom client, modèle véhicule..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-slate-950 border border-slate-700/80 rounded-lg text-xs text-slate-100 pl-9 pr-3 py-2 placeholder-slate-500 focus:outline-none focus:border-amber-500 font-sans"
          />
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400 font-mono">Étape:</span>
          <select
            value={stageFilter}
            onChange={(e) => setStageFilter(e.target.value)}
            className="bg-slate-950 border border-slate-700 rounded-lg text-xs text-slate-200 px-3 py-2 focus:outline-none focus:border-amber-500 font-sans"
          >
            <option value="ALL">Toutes les étapes</option>
            <option value="NEW">NEW (Nouveau)</option>
            <option value="QUALIFIED">QUALIFIED (Qualifié)</option>
            <option value="QUOTE_SENT">QUOTE_SENT (Devis Envoyé)</option>
            <option value="FCR_VERIFIED">FCR_VERIFIED (FCR Validé)</option>
          </select>
        </div>
      </div>

      {/* Lead Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-950/80 text-slate-400 font-mono text-[10px] uppercase border-b border-slate-800">
            <tr>
              <th className="p-3">Client</th>
              <th className="p-3">Modèle Recherché</th>
              <th className="p-3">Budget Estimé (€)</th>
              <th className="p-3">Étape Pipeline</th>
              <th className="p-3">Conseiller Commercial</th>
              <th className="p-3 font-mono">Dernière MàJ</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/80 text-slate-200">
            {filteredLeads.length === 0 ? (
              <tr>
                <td colSpan={6} className="p-8 text-center text-slate-500">
                  Aucun lead trouvé dans ce filtre.
                </td>
              </tr>
            ) : (
              filteredLeads.map((l) => (
                <tr key={l.id} className="hover:bg-slate-800/40 transition-colors">
                  <td className="p-3 font-semibold text-slate-100">{l.customerName}</td>

                  <td className="p-3">
                    <div className="flex items-center gap-1.5 font-medium text-slate-200">
                      <Car className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" />
                      <span>{l.targetVehicle || "Non spécifié"}</span>
                    </div>
                  </td>

                  <td className="p-3 font-mono text-emerald-400 font-semibold">
                    {l.budgetMinEur ? `${l.budgetMinEur.toLocaleString()} € - ${l.budgetMaxEur?.toLocaleString()} €` : "—"}
                  </td>

                  <td className="p-3">
                    <span className={`px-2 py-0.5 text-[10px] font-mono font-bold rounded border ${getStageColor(l.stage)}`}>
                      {l.stage}
                    </span>
                  </td>

                  <td className="p-3">
                    <div className="flex items-center gap-1 text-slate-300">
                      <UserCheck className="w-3 h-3 text-slate-500" />
                      <span>{l.assignedAgentName || "Non attribué"}</span>
                    </div>
                  </td>

                  <td className="p-3 font-mono text-slate-400 text-[11px]">
                    {new Date(l.updatedAt).toLocaleDateString("fr-FR")}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
