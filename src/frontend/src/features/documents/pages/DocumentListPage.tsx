import React, { useState } from "react";
import { ShieldCheck, Search, FileText, Download, AlertTriangle, CheckCircle, Clock } from "lucide-react";

interface DocumentRecord {
  id: string;
  filename: string;
  category: "CARTE_GRISE" | "FCR_CERTIFICATE" | "PASSPORT" | "CUSTOMS_FORM";
  mimeType: string;
  sizeBytes: number;
  sha256Checksum: string;
  scanStatus: "PASSED" | "PENDING_SCAN" | "QUARANTINED";
  uploadedBy: string;
  createdAt: string;
}

const MOCK_DOCUMENTS: DocumentRecord[] = [
  {
    id: "doc_001",
    filename: "Carte_Grise_BMW_X5_WBA123.pdf",
    category: "CARTE_GRISE",
    mimeType: "application/pdf",
    sizeBytes: 2450000,
    sha256Checksum: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    scanStatus: "PASSED",
    uploadedBy: "Mohamed Ben Ali",
    createdAt: "2026-09-13T10:00:00Z",
  },
  {
    id: "doc_002",
    filename: "Attestation_FCR_TRE_Mohamed_BenAli.pdf",
    category: "FCR_CERTIFICATE",
    mimeType: "application/pdf",
    sizeBytes: 1850000,
    sha256Checksum: "f4c8996fb92427ae41e4649b934ca495991b7852b855e3b0c44298fc1c149afb",
    scanStatus: "PASSED",
    uploadedBy: "Sami Khedira",
    createdAt: "2026-09-13T11:15:00Z",
  },
  {
    id: "doc_003",
    filename: "Passeport_Scan_Karim_Mansour.pdf",
    category: "PASSPORT",
    mimeType: "application/pdf",
    sizeBytes: 3100000,
    sha256Checksum: "9b7852b855e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991",
    scanStatus: "PENDING_SCAN",
    uploadedBy: "Karim Mansour",
    createdAt: "2026-09-13T16:50:00Z",
  },
];

export const DocumentListPage: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("ALL");

  const filteredDocs = MOCK_DOCUMENTS.filter((d) => {
    const matchesSearch =
      d.filename.toLowerCase().includes(searchQuery.toLowerCase()) ||
      d.uploadedBy.toLowerCase().includes(searchQuery.toLowerCase());

    if (categoryFilter !== "ALL") return matchesSearch && d.category === categoryFilter;
    return matchesSearch;
  });

  const getScanBadge = (status: string) => {
    switch (status) {
      case "PASSED":
        return (
          <span className="px-2 py-0.5 text-[10px] font-mono bg-emerald-950 text-emerald-400 border border-emerald-800 rounded-full flex items-center gap-1 w-max">
            <CheckCircle className="w-3 h-3" />
            PASSED (SHA-256 Valid)
          </span>
        );
      case "PENDING_SCAN":
        return (
          <span className="px-2 py-0.5 text-[10px] font-mono bg-amber-950 text-amber-400 border border-amber-800 rounded-full flex items-center gap-1 w-max">
            <Clock className="w-3 h-3 animate-spin" />
            PENDING SCAN
          </span>
        );
      case "QUARANTINED":
        return (
          <span className="px-2 py-0.5 text-[10px] font-mono bg-red-950 text-red-400 border border-red-800 rounded-full flex items-center gap-1 w-max">
            <AlertTriangle className="w-3 h-3" />
            QUARANTINED
          </span>
        );
      default:
        return null;
    }
  };

  const formatMB = (bytes: number) => (bytes / (1024 * 1024)).toFixed(2) + " MB";

  return (
    <div className="flex-1 flex flex-col bg-slate-950 p-6 overflow-y-auto font-sans text-slate-100 select-none">
      {/* Header Bar */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-6 h-6 text-purple-400" />
            <h1 className="text-xl font-bold text-slate-100">Dépôt Privé S3 & Documents RGPD</h1>
          </div>
          <p className="text-xs text-slate-400 mt-1 font-mono">
            Stockage S3 sécurisé, URLs pré-signées 15 min et vérification SHA-256 malware (BR-013)
          </p>
        </div>
      </div>

      {/* Filter & Search Toolbar */}
      <div className="bg-slate-900 p-4 rounded-xl border border-slate-800 mb-6 flex items-center justify-between gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
          <input
            type="text"
            placeholder="Rechercher nom de fichier, uploader..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-slate-950 border border-slate-700/80 rounded-lg text-xs text-slate-100 pl-9 pr-3 py-2 placeholder-slate-500 focus:outline-none focus:border-purple-500 font-sans"
          />
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400 font-mono">Catégorie:</span>
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="bg-slate-950 border border-slate-700 rounded-lg text-xs text-slate-200 px-3 py-2 focus:outline-none focus:border-purple-500 font-sans"
          >
            <option value="ALL">Toutes les catégories</option>
            <option value="CARTE_GRISE">Carte Grise</option>
            <option value="FCR_CERTIFICATE">Certificat FCR (TRE)</option>
            <option value="PASSPORT">Passeport</option>
            <option value="CUSTOMS_FORM">Formulaire Douane</option>
          </select>
        </div>
      </div>

      {/* Document Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-950/80 text-slate-400 font-mono text-[10px] uppercase border-b border-slate-800">
            <tr>
              <th className="p-3">Fichier</th>
              <th className="p-3">Catégorie</th>
              <th className="p-3">Taille</th>
              <th className="p-3">Statut Scan S3</th>
              <th className="p-3">Déposé Par</th>
              <th className="p-3 text-right">Accès Sécurisé</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/80 text-slate-200">
            {filteredDocs.length === 0 ? (
              <tr>
                <td colSpan={6} className="p-8 text-center text-slate-500">
                  Aucun document trouvé dans ce filtre.
                </td>
              </tr>
            ) : (
              filteredDocs.map((d) => (
                <tr key={d.id} className="hover:bg-slate-800/40 transition-colors">
                  <td className="p-3">
                    <div className="flex items-center gap-2 font-medium text-slate-100">
                      <FileText className="w-4 h-4 text-purple-400 flex-shrink-0" />
                      <span>{d.filename}</span>
                    </div>
                    <div className="text-[9px] text-slate-500 font-mono truncate max-w-xs mt-0.5">
                      SHA: {d.sha256Checksum}
                    </div>
                  </td>

                  <td className="p-3">
                    <span className="px-2 py-0.5 text-[10px] bg-slate-800 text-slate-300 border border-slate-700 rounded font-mono">
                      {d.category}
                    </span>
                  </td>

                  <td className="p-3 font-mono text-slate-300">{formatMB(d.sizeBytes)}</td>

                  <td className="p-3">{getScanBadge(d.scanStatus)}</td>

                  <td className="p-3 text-slate-300">{d.uploadedBy}</td>

                  <td className="p-3 text-right">
                    {d.scanStatus === "PASSED" ? (
                      <button
                        type="button"
                        onClick={() => alert("Génération URL pre-signed 15min S3...")}
                        className="px-2.5 py-1 text-[11px] bg-purple-600/30 hover:bg-purple-600/50 text-purple-300 border border-purple-500/50 rounded transition-colors flex items-center gap-1 ml-auto"
                      >
                        <Download className="w-3 h-3" />
                        Télécharger (Pre-signed)
                      </button>
                    ) : (
                      <span className="text-[10px] text-slate-500 font-mono italic">Accès Bloqué (Scan)</span>
                    )}
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
