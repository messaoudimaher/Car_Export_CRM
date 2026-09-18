import React, { useState } from "react";
import { Users, Search, Phone, Mail, Globe, ShieldCheck, MessageSquare, Plus, Pencil, X, Save } from "lucide-react";
import { CustomerContext } from "../../inbox/types";

const MOCK_CUSTOMERS: CustomerContext[] = [
  {
    id: "cust_991",
    fullName: "Mohamed Ben Ali",
    phoneE164: "+21698123456",
    email: "m.benali@gmail.com",
    country: "Tunisia",
    fcrEligible: true,
    notes: "Client sérieux. Privilégie SUV allemand récent.",
    createdAt: "2026-08-10T10:00:00Z",
  },
  {
    id: "cust_992",
    fullName: "Youssef Trabelsi",
    phoneE164: "+21622987654",
    email: "y.trabelsi@yahoo.fr",
    country: "Tunisia",
    fcrEligible: false,
    notes: "Demande d'information délais transport maritime.",
    createdAt: "2026-09-12T14:20:00Z",
  },
  {
    id: "cust_993",
    fullName: "Karim Mansour",
    phoneE164: "+33612345678",
    email: "karim.m@outlook.fr",
    country: "France / Tunisia",
    fcrEligible: true,
    notes: "Résident en France (TRE), droit FCR confirmé.",
    createdAt: "2026-09-01T09:15:00Z",
  },
];

export const CustomerListPage: React.FC = () => {
  const [customers, setCustomers] = useState<CustomerContext[]>(MOCK_CUSTOMERS);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterFcr, setFilterFcr] = useState<"ALL" | "FCR_ONLY" | "STANDARD">("ALL");

  // Modal state: null = closed, "create" = new, or customer id for edit
  const [modalMode, setModalMode] = useState<null | "create" | string>(null);
  const [editForm, setEditForm] = useState({ fullName: "", email: "", country: "", fcrEligible: false });
  const [saveSuccess, setSaveSuccess] = useState(false);

  const filteredCustomers = customers.filter((c) => {
    const matchesSearch =
      c.fullName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.phoneE164.includes(searchQuery) ||
      (c.email && c.email.toLowerCase().includes(searchQuery.toLowerCase()));

    if (filterFcr === "FCR_ONLY") return matchesSearch && c.fcrEligible;
    if (filterFcr === "STANDARD") return matchesSearch && !c.fcrEligible;
    return matchesSearch;
  });

  const openEditModal = (c: CustomerContext) => {
    setEditForm({ fullName: c.fullName, email: c.email || "", country: c.country, fcrEligible: c.fcrEligible });
    setSaveSuccess(false);
    setModalMode(c.id);
  };

  const openCreateModal = () => {
    setEditForm({ fullName: "", email: "", country: "Tunisia", fcrEligible: false });
    setSaveSuccess(false);
    setModalMode("create");
  };

  const closeModal = () => { setModalMode(null); setSaveSuccess(false); };

  const handleSave = () => {
    if (!editForm.fullName.trim()) return;
    const now = new Date().toISOString();
    if (modalMode === "create") {
      const newCustomer: CustomerContext = {
        id: `cust_${Date.now()}`,
        fullName: editForm.fullName.trim(),
        email: editForm.email.trim() || undefined,
        country: editForm.country.trim() || "Tunisia",
        phoneE164: "+216 -- --- ---",
        fcrEligible: editForm.fcrEligible,
        notes: "",
        createdAt: now,
      };
      setCustomers((prev) => [newCustomer, ...prev]);
    } else {
      setCustomers((prev) =>
        prev.map((c) =>
          c.id === modalMode
            ? { ...c, fullName: editForm.fullName.trim(), email: editForm.email.trim() || undefined, country: editForm.country.trim() || "Tunisia", fcrEligible: editForm.fcrEligible }
            : c
        )
      );
    }
    setSaveSuccess(true);
    setTimeout(closeModal, 800);
  };

  return (
    <div className="flex-1 flex flex-col bg-slate-950 p-6 overflow-y-auto font-sans text-slate-100 select-none">
      {/* Header Bar */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="flex items-center gap-2">
            <Users className="w-6 h-6 text-blue-400" />
            <h1 className="text-xl font-bold text-slate-100">Répertoire des Clients</h1>
          </div>
          <p className="text-xs text-slate-400 mt-1 font-mono">
            Gestion centralisée des acheteurs et éligibilité FCR (TRE)
          </p>
        </div>

        <button
          type="button"
          onClick={openCreateModal}
          className="px-3.5 py-2 text-xs bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg transition-colors flex items-center gap-1.5 shadow-sm"
        >
          <Plus className="w-4 h-4" />
          Nouveau Client
        </button>
      </div>

      {/* Filter & Search Toolbar */}
      <div className="bg-slate-900 p-4 rounded-xl border border-slate-800 mb-6 flex items-center justify-between gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
          <input
            type="text"
            placeholder="Rechercher nom, téléphone E.164, email..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-slate-950 border border-slate-700/80 rounded-lg text-xs text-slate-100 pl-9 pr-3 py-2 placeholder-slate-500 focus:outline-none focus:border-blue-500 font-sans"
          />
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setFilterFcr("ALL")}
            className={`px-3 py-1.5 text-xs rounded-lg font-medium transition-colors ${
              filterFcr === "ALL"
                ? "bg-blue-600/30 text-blue-300 border border-blue-500/50"
                : "bg-slate-800 text-slate-400 hover:text-slate-200"
            }`}
          >
            Tous ({MOCK_CUSTOMERS.length})
          </button>
          <button
            type="button"
            onClick={() => setFilterFcr("FCR_ONLY")}
            className={`px-3 py-1.5 text-xs rounded-lg font-medium transition-colors ${
              filterFcr === "FCR_ONLY"
                ? "bg-emerald-600/30 text-emerald-300 border border-emerald-500/50"
                : "bg-slate-800 text-slate-400 hover:text-slate-200"
            }`}
          >
            FCR Éligibles
          </button>
          <button
            type="button"
            onClick={() => setFilterFcr("STANDARD")}
            className={`px-3 py-1.5 text-xs rounded-lg font-medium transition-colors ${
              filterFcr === "STANDARD"
                ? "bg-slate-700 text-slate-200 border border-slate-600"
                : "bg-slate-800 text-slate-400 hover:text-slate-200"
            }`}
          >
            Régime Commun
          </button>
        </div>
      </div>

      {/* Directory Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-950/80 text-slate-400 font-mono text-[10px] uppercase border-b border-slate-800">
            <tr>
              <th className="p-3">Client</th>
              <th className="p-3">Téléphone E.164</th>
              <th className="p-3">Pays</th>
              <th className="p-3">Éligibilité FCR</th>
              <th className="p-3">Créé Le</th>
              <th className="p-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/80 text-slate-200">
            {filteredCustomers.length === 0 ? (
              <tr>
                <td colSpan={6} className="p-8 text-center text-slate-500">
                  Aucun client trouvé pour ce filtre.
                </td>
              </tr>
            ) : (
              filteredCustomers.map((c) => (
                <tr key={c.id} className="hover:bg-slate-800/40 transition-colors">
                  <td className="p-3">
                    <div className="font-semibold text-slate-100">{c.fullName}</div>
                    <div className="text-[11px] text-slate-400 flex items-center gap-1 font-mono mt-0.5">
                      <Mail className="w-3 h-3 text-slate-500" />
                      <span>{c.email || "Non renseigné"}</span>
                    </div>
                  </td>

                  <td className="p-3 font-mono text-slate-300">
                    <div className="flex items-center gap-1">
                      <Phone className="w-3 h-3 text-slate-500" />
                      <span>{c.phoneE164}</span>
                    </div>
                  </td>

                  <td className="p-3">
                    <div className="flex items-center gap-1 text-slate-300">
                      <Globe className="w-3 h-3 text-slate-500" />
                      <span>{c.country}</span>
                    </div>
                  </td>

                  <td className="p-3">
                    {c.fcrEligible ? (
                      <span className="px-2 py-0.5 text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-800/80 rounded-full font-mono flex items-center gap-1 w-max">
                        <ShieldCheck className="w-3 h-3" />
                        FCR TRE Éligible
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 text-[10px] bg-slate-800 text-slate-400 border border-slate-700 rounded-full font-mono w-max block">
                        Régime Commun
                      </span>
                    )}
                  </td>

                  <td className="p-3 font-mono text-slate-400 text-[11px]">
                    {new Date(c.createdAt).toLocaleDateString("fr-FR")}
                  </td>

                  <td className="p-3 text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      <button
                        type="button"
                        onClick={() => openEditModal(c)}
                        className="px-2 py-1 text-[11px] bg-slate-800 hover:bg-slate-700 text-amber-400 rounded border border-slate-700 transition-colors flex items-center gap-1"
                      >
                        <Pencil className="w-3 h-3" />
                        Modifier
                      </button>
                      <button
                        type="button"
                        className="px-2.5 py-1 text-[11px] bg-slate-800 hover:bg-slate-700 text-blue-400 rounded border border-slate-700 transition-colors flex items-center gap-1"
                      >
                        <MessageSquare className="w-3 h-3" />
                        Ouvrir Chat
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Create / Edit Customer Modal */}
      {modalMode !== null && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl w-full max-w-md shadow-2xl font-sans text-slate-100">
            <div className="flex items-center justify-between p-4 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Users className="w-4 h-4 text-blue-400" />
                <h2 className="text-sm font-bold">{modalMode === "create" ? "Nouveau Client" : "Modifier le Client"}</h2>
              </div>
              <button onClick={closeModal} className="text-slate-400 hover:text-slate-200"><X className="w-5 h-5" /></button>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <label className="text-[10px] text-slate-400 block mb-1 uppercase font-mono">Nom Complet *</label>
                <input type="text" value={editForm.fullName} onChange={(e) => setEditForm((f) => ({ ...f, fullName: e.target.value }))} placeholder="Ex: Mohamed Ben Ali" className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-xs text-slate-100 focus:outline-none focus:border-blue-500" />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 block mb-1 uppercase font-mono">Email</label>
                <input type="email" value={editForm.email} onChange={(e) => setEditForm((f) => ({ ...f, email: e.target.value }))} placeholder="Ex: client@gmail.com" className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-xs text-slate-100 focus:outline-none focus:border-blue-500" />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 block mb-1 uppercase font-mono">Pays</label>
                <select value={editForm.country} onChange={(e) => setEditForm((f) => ({ ...f, country: e.target.value }))} className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500">
                  <option value="Tunisia">Tunisie</option>
                  <option value="France / Tunisia">France / Tunisie (TRE)</option>
                  <option value="Germany">Allemagne</option>
                  <option value="Other">Autre</option>
                </select>
              </div>
              <div className="flex items-center gap-3 p-3 bg-slate-950 rounded border border-slate-800">
                <input type="checkbox" id="fcr-eligible-check" checked={editForm.fcrEligible} onChange={(e) => setEditForm((f) => ({ ...f, fcrEligible: e.target.checked }))} className="w-4 h-4 accent-emerald-500" />
                <label htmlFor="fcr-eligible-check" className="text-xs text-slate-200 cursor-pointer">
                  Client éligible au régime FCR TRE (Transfert Résidents à l'Étranger)
                </label>
              </div>
            </div>
            <div className="flex items-center justify-between p-4 border-t border-slate-800">
              <button type="button" onClick={closeModal} className="px-3 py-1.5 text-xs bg-slate-800 text-slate-300 rounded hover:bg-slate-700 transition-colors">Annuler</button>
              <button type="button" onClick={handleSave} disabled={saveSuccess} className={`px-4 py-1.5 text-xs font-medium rounded transition-colors flex items-center gap-1.5 ${saveSuccess ? "bg-emerald-600 text-white cursor-default" : "bg-blue-600 hover:bg-blue-500 text-white"}`}>
                <Save className="w-3.5 h-3.5" />
                {saveSuccess ? "✓ Enregistré !" : modalMode === "create" ? "Créer le Client" : "Enregistrer"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
