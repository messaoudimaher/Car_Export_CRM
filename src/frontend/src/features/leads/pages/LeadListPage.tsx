import React, { useState } from "react";
import { Layers, Search, Car, UserCheck, Plus, X, Save, Pencil } from "lucide-react";
import { LeadContext } from "../../inbox/types";

type Lead = LeadContext & { customerName: string };

const INITIAL_LEADS: Lead[] = [
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

const STAGES = ["NEW", "QUALIFIED", "QUOTE_SENT", "FCR_VERIFIED", "WON", "LOST"] as const;
type Stage = typeof STAGES[number];

interface LeadFormData {
  customerName: string;
  targetVehicle: string;
  budgetMinEur: string;
  budgetMaxEur: string;
  stage: Stage;
  assignedAgentName: string;
}

const EMPTY_FORM: LeadFormData = {
  customerName: "",
  targetVehicle: "",
  budgetMinEur: "",
  budgetMaxEur: "",
  stage: "NEW",
  assignedAgentName: "Non attribué",
};

export const LeadListPage: React.FC = () => {
  const [leads, setLeads] = useState<Lead[]>(INITIAL_LEADS);
  const [searchQuery, setSearchQuery] = useState("");
  const [stageFilter, setStageFilter] = useState<string>("ALL");
  const [modalMode, setModalMode] = useState<null | "create" | string>(null);
  const [formData, setFormData] = useState<LeadFormData>(EMPTY_FORM);
  const [formErrors, setFormErrors] = useState<Partial<LeadFormData>>({});
  const [saveSuccess, setSaveSuccess] = useState(false);

  const filteredLeads = leads.filter((l) => {
    const matchesSearch =
      l.customerName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (l.targetVehicle && l.targetVehicle.toLowerCase().includes(searchQuery.toLowerCase()));
    if (stageFilter !== "ALL") return matchesSearch && l.stage === stageFilter;
    return matchesSearch;
  });

  const getStageColor = (stage: string) => {
    switch (stage) {
      case "NEW": return "bg-blue-950 text-blue-400 border-blue-800";
      case "QUALIFIED": return "bg-amber-950 text-amber-400 border-amber-800";
      case "QUOTE_SENT": return "bg-purple-950 text-purple-400 border-purple-800";
      case "FCR_VERIFIED": return "bg-emerald-950 text-emerald-400 border-emerald-800";
      case "WON": return "bg-emerald-900 text-emerald-200 border-emerald-700";
      case "LOST": return "bg-rose-950 text-rose-400 border-rose-800";
      default: return "bg-slate-800 text-slate-300 border-slate-700";
    }
  };

  const openCreateModal = () => {
    setFormData(EMPTY_FORM);
    setFormErrors({});
    setSaveSuccess(false);
    setModalMode("create");
  };

  const openEditModal = (lead: Lead) => {
    setFormData({
      customerName: lead.customerName,
      targetVehicle: lead.targetVehicle || "",
      budgetMinEur: lead.budgetMinEur?.toString() || "",
      budgetMaxEur: lead.budgetMaxEur?.toString() || "",
      stage: lead.stage as Stage,
      assignedAgentName: lead.assignedAgentName || "Non attribué",
    });
    setFormErrors({});
    setSaveSuccess(false);
    setModalMode(lead.id);
  };

  const closeModal = () => { setModalMode(null); setSaveSuccess(false); };

  const validate = (): boolean => {
    const errors: Partial<LeadFormData> = {};
    if (!formData.customerName.trim()) errors.customerName = "Nom client requis";
    if (!formData.targetVehicle.trim()) errors.targetVehicle = "Véhicule requis";
    if (!formData.budgetMinEur || isNaN(Number(formData.budgetMinEur))) errors.budgetMinEur = "Budget min invalide";
    if (!formData.budgetMaxEur || isNaN(Number(formData.budgetMaxEur))) errors.budgetMaxEur = "Budget max invalide";
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSave = () => {
    if (!validate()) return;
    const now = new Date().toISOString();
    if (modalMode === "create") {
      const newLead: Lead = {
        id: `lead_${Date.now()}`,
        customerId: `cust_${Date.now()}`,
        customerName: formData.customerName.trim(),
        stage: formData.stage,
        targetVehicle: formData.targetVehicle.trim(),
        budgetMinEur: Number(formData.budgetMinEur),
        budgetMaxEur: Number(formData.budgetMaxEur),
        assignedAgentName: formData.assignedAgentName || "Non attribué",
        updatedAt: now,
      };
      setLeads((prev) => [newLead, ...prev]);
    } else {
      setLeads((prev) =>
        prev.map((l) =>
          l.id === modalMode
            ? { ...l, customerName: formData.customerName.trim(), stage: formData.stage, targetVehicle: formData.targetVehicle.trim(), budgetMinEur: Number(formData.budgetMinEur), budgetMaxEur: Number(formData.budgetMaxEur), assignedAgentName: formData.assignedAgentName || "Non attribué", updatedAt: now }
            : l
        )
      );
    }
    setSaveSuccess(true);
    setTimeout(closeModal, 800);
  };

  return (
    <div className="flex-1 flex flex-col bg-slate-950 p-6 overflow-y-auto font-sans text-slate-100 select-none">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="flex items-center gap-2">
            <Layers className="w-6 h-6 text-amber-400" />
            <h1 className="text-xl font-bold text-slate-100">Pipeline des Opportunités (Leads)</h1>
          </div>
          <p className="text-xs text-slate-400 mt-1 font-mono">Suivi des demandes d'achat et devis d'exportation Allemagne ➔ Tunisie</p>
        </div>
        <button type="button" onClick={openCreateModal} className="px-3.5 py-2 text-xs bg-amber-600 hover:bg-amber-500 text-white font-medium rounded-lg transition-colors flex items-center gap-1.5 shadow-sm">
          <Plus className="w-4 h-4" />
          Nouveau Lead
        </button>
      </div>

      {/* Search & Filter */}
      <div className="bg-slate-900 p-4 rounded-xl border border-slate-800 mb-6 flex items-center justify-between gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
          <input type="text" placeholder="Rechercher nom client, modèle véhicule..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="w-full bg-slate-950 border border-slate-700/80 rounded-lg text-xs text-slate-100 pl-9 pr-3 py-2 placeholder-slate-500 focus:outline-none focus:border-amber-500 font-sans" />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400 font-mono">Étape:</span>
          <select value={stageFilter} onChange={(e) => setStageFilter(e.target.value)} className="bg-slate-950 border border-slate-700 rounded-lg text-xs text-slate-200 px-3 py-2 focus:outline-none focus:border-amber-500 font-sans">
            <option value="ALL">Toutes les étapes</option>
            {STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-950/80 text-slate-400 font-mono text-[10px] uppercase border-b border-slate-800">
            <tr>
              <th className="p-3">Client</th>
              <th className="p-3">Modèle Recherché</th>
              <th className="p-3">Budget Estimé (€)</th>
              <th className="p-3">Étape Pipeline</th>
              <th className="p-3">Conseiller Commercial</th>
              <th className="p-3">Dernière MàJ</th>
              <th className="p-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/80 text-slate-200">
            {filteredLeads.length === 0 ? (
              <tr><td colSpan={7} className="p-8 text-center text-slate-500">Aucun lead trouvé dans ce filtre.</td></tr>
            ) : (
              filteredLeads.map((l) => (
                <tr key={l.id} className="hover:bg-slate-800/40 transition-colors">
                  <td className="p-3 font-semibold text-slate-100">{l.customerName}</td>
                  <td className="p-3"><div className="flex items-center gap-1.5 font-medium text-slate-200"><Car className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" /><span>{l.targetVehicle || "Non spécifié"}</span></div></td>
                  <td className="p-3 font-mono text-emerald-400 font-semibold">{l.budgetMinEur ? `${l.budgetMinEur.toLocaleString()} € - ${l.budgetMaxEur?.toLocaleString()} €` : "—"}</td>
                  <td className="p-3"><span className={`px-2 py-0.5 text-[10px] font-mono font-bold rounded border ${getStageColor(l.stage)}`}>{l.stage}</span></td>
                  <td className="p-3"><div className="flex items-center gap-1 text-slate-300"><UserCheck className="w-3 h-3 text-slate-500" /><span>{l.assignedAgentName || "Non attribué"}</span></div></td>
                  <td className="p-3 font-mono text-slate-400 text-[11px]">{new Date(l.updatedAt).toLocaleDateString("fr-FR")}</td>
                  <td className="p-3 text-right">
                    <button type="button" onClick={() => openEditModal(l)} className="px-2.5 py-1 text-[11px] bg-slate-800 hover:bg-slate-700 text-amber-400 rounded border border-slate-700 transition-colors inline-flex items-center gap-1">
                      <Pencil className="w-3 h-3" />
                      Modifier
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Create / Edit Modal */}
      {modalMode !== null && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl w-full max-w-lg shadow-2xl font-sans text-slate-100">
            <div className="flex items-center justify-between p-4 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-amber-400" />
                <h2 className="text-sm font-bold">{modalMode === "create" ? "Créer un Nouveau Lead" : "Modifier le Lead"}</h2>
              </div>
              <button onClick={closeModal} className="text-slate-400 hover:text-slate-200"><X className="w-5 h-5" /></button>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <label className="text-[10px] text-slate-400 block mb-1 uppercase font-mono">Nom du Client *</label>
                <input type="text" value={formData.customerName} onChange={(e) => setFormData((f) => ({ ...f, customerName: e.target.value }))} placeholder="Ex: Mohamed Ben Ali" className={`w-full bg-slate-950 border rounded p-2 text-xs text-slate-100 focus:outline-none ${formErrors.customerName ? "border-rose-500" : "border-slate-700 focus:border-amber-500"}`} />
                {formErrors.customerName && <p className="text-[10px] text-rose-400 mt-0.5">{formErrors.customerName}</p>}
              </div>
              <div>
                <label className="text-[10px] text-slate-400 block mb-1 uppercase font-mono">Véhicule Recherché *</label>
                <input type="text" value={formData.targetVehicle} onChange={(e) => setFormData((f) => ({ ...f, targetVehicle: e.target.value }))} placeholder="Ex: BMW X5 xDrive30d 2022" className={`w-full bg-slate-950 border rounded p-2 text-xs text-slate-100 focus:outline-none ${formErrors.targetVehicle ? "border-rose-500" : "border-slate-700 focus:border-amber-500"}`} />
                {formErrors.targetVehicle && <p className="text-[10px] text-rose-400 mt-0.5">{formErrors.targetVehicle}</p>}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-slate-400 block mb-1 uppercase font-mono">Budget Min (€) *</label>
                  <input type="number" value={formData.budgetMinEur} onChange={(e) => setFormData((f) => ({ ...f, budgetMinEur: e.target.value }))} placeholder="30000" className={`w-full bg-slate-950 border rounded p-2 text-xs text-slate-100 font-mono focus:outline-none ${formErrors.budgetMinEur ? "border-rose-500" : "border-slate-700 focus:border-amber-500"}`} />
                  {formErrors.budgetMinEur && <p className="text-[10px] text-rose-400 mt-0.5">{formErrors.budgetMinEur}</p>}
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 block mb-1 uppercase font-mono">Budget Max (€) *</label>
                  <input type="number" value={formData.budgetMaxEur} onChange={(e) => setFormData((f) => ({ ...f, budgetMaxEur: e.target.value }))} placeholder="45000" className={`w-full bg-slate-950 border rounded p-2 text-xs text-slate-100 font-mono focus:outline-none ${formErrors.budgetMaxEur ? "border-rose-500" : "border-slate-700 focus:border-amber-500"}`} />
                  {formErrors.budgetMaxEur && <p className="text-[10px] text-rose-400 mt-0.5">{formErrors.budgetMaxEur}</p>}
                </div>
              </div>
              <div>
                <label className="text-[10px] text-slate-400 block mb-1 uppercase font-mono">Étape Pipeline</label>
                <select value={formData.stage} onChange={(e) => setFormData((f) => ({ ...f, stage: e.target.value as Stage }))} className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-xs text-slate-200 focus:outline-none focus:border-amber-500 font-mono">
                  {STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label className="text-[10px] text-slate-400 block mb-1 uppercase font-mono">Conseiller Commercial</label>
                <select value={formData.assignedAgentName} onChange={(e) => setFormData((f) => ({ ...f, assignedAgentName: e.target.value }))} className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-xs text-slate-200 focus:outline-none focus:border-amber-500 font-sans">
                  <option value="Non attribué">Non attribué</option>
                  <option value="Sami Khedira">Sami Khedira</option>
                  <option value="Maher Messaoudi">Maher Messaoudi</option>
                </select>
              </div>
            </div>
            <div className="flex items-center justify-between p-4 border-t border-slate-800">
              <button type="button" onClick={closeModal} className="px-3 py-1.5 text-xs bg-slate-800 text-slate-300 rounded hover:bg-slate-700 transition-colors">Annuler</button>
              <button type="button" onClick={handleSave} disabled={saveSuccess} className={`px-4 py-1.5 text-xs font-medium rounded transition-colors flex items-center gap-1.5 ${saveSuccess ? "bg-emerald-600 text-white cursor-default" : "bg-amber-600 hover:bg-amber-500 text-white"}`}>
                <Save className="w-3.5 h-3.5" />
                {saveSuccess ? "✓ Enregistré !" : modalMode === "create" ? "Créer le Lead" : "Enregistrer"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

