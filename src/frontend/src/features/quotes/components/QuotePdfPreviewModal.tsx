import React, { useState } from "react";
import { X, Download, Send, FileText, ShieldCheck } from "lucide-react";

interface QuotePdfPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  customerName: string;
  totalPriceEur: number;
  onSendToWhatsApp: () => void;
}

export const QuotePdfPreviewModal: React.FC<QuotePdfPreviewModalProps> = ({
  isOpen,
  onClose,
  customerName,
  totalPriceEur,
  onSendToWhatsApp,
}) => {
  const [downloadSuccess, setDownloadSuccess] = useState(false);
  if (!isOpen) return null;

  const handleDownload = () => {
    setDownloadSuccess(true);
    setTimeout(() => setDownloadSuccess(false), 2500);
  };

  return (
    <div className="fixed inset-0 z-[60] bg-slate-950/85 backdrop-blur-md flex items-center justify-center p-4 animate-fade-in">
      <div className="w-[720px] max-h-[90vh] bg-slate-900 border border-slate-800 rounded-xl flex flex-col shadow-2xl overflow-hidden text-slate-100 select-none font-sans">
        {/* Modal Header */}
        <div className="p-4 bg-slate-950 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-emerald-400" />
            <div>
              <h2 className="text-sm font-bold text-slate-100">Aperçu PDF Devis Officiel FCR (Pre-signed S3)</h2>
              <p className="text-[10px] text-slate-400 font-mono">Autorisation valide 15 minutes • Tenant ID scoped</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-slate-200 rounded hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body - Simulated Document Preview Sheet */}
        <div className="flex-1 overflow-y-auto p-6 bg-slate-950/60 flex justify-center">
          <div className="w-[580px] bg-slate-900 border border-slate-700/80 rounded-lg p-6 space-y-6 text-xs text-slate-200 shadow-xl">
            {/* Header Document Brand */}
            <div className="flex justify-between items-start border-b border-slate-800 pb-4">
              <div>
                <h1 className="text-lg font-black text-blue-400 tracking-wider">CAR-EXPORT-CRM</h1>
                <p className="text-[10px] text-slate-400 font-mono">Exportation Véhicules Allemagne ➔ Tunisie</p>
                <p className="text-[10px] text-slate-400">Munich / Stuttgart / Tunis</p>
              </div>
              <div className="text-right font-mono text-[10px] text-slate-400 space-y-0.5">
                <div className="font-bold text-slate-200 text-xs">DEVIS N° #FCR-2026-0982</div>
                <div>Date: {new Date().toLocaleDateString("fr-FR")}</div>
                <div>Expire: {new Date(Date.now() + 30 * 86400000).toLocaleDateString("fr-FR")}</div>
              </div>
            </div>

            {/* Customer & Dest Info */}
            <div className="grid grid-cols-2 gap-4 bg-slate-950 p-3 rounded border border-slate-800 text-xs">
              <div>
                <span className="text-[10px] text-slate-500 uppercase font-mono block mb-1">Destinataire / Client:</span>
                <span className="font-bold text-slate-100 block">{customerName}</span>
                <span className="text-slate-400 block text-[11px]">Régime: Exonération Douane FCR TRE</span>
              </div>
              <div className="text-right">
                <span className="text-[10px] text-slate-500 uppercase font-mono block mb-1">Port de Destination:</span>
                <span className="font-semibold text-slate-200 block">Port de La Goulette (Tunis)</span>
                <span className="text-slate-400 block text-[11px]">Transport Maritime RORO</span>
              </div>
            </div>

            {/* Line Items Table */}
            <div className="border border-slate-800 rounded overflow-hidden">
              <table className="w-full text-left text-xs font-sans">
                <thead className="bg-slate-950 text-slate-400 font-mono text-[10px] uppercase border-b border-slate-800">
                  <tr>
                    <th className="p-2">Désignation</th>
                    <th className="p-2 text-center">Régime TVA</th>
                    <th className="p-2 text-right">Montant HT (€)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800 text-slate-200">
                  <tr>
                    <td className="p-2 font-medium">BMW X5 xDrive30d M Sport (2022) - VIN #WBA123...</td>
                    <td className="p-2 text-center font-mono text-emerald-400">Netto (0%)</td>
                    <td className="p-2 text-right font-mono">45 000 €</td>
                  </tr>
                  <tr>
                    <td className="p-2 font-medium">Frais de Transport Maritime & Logistique Export</td>
                    <td className="p-2 text-center font-mono text-slate-400">Exempt</td>
                    <td className="p-2 text-right font-mono">1 200 €</td>
                  </tr>
                  <tr>
                    <td className="p-2 font-medium">Frais de Gestion Administrateur & Certificat EUR.1</td>
                    <td className="p-2 text-center font-mono text-slate-400">Exempt</td>
                    <td className="p-2 text-right font-mono">800 €</td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Price Summary Footer */}
            <div className="bg-slate-950 p-4 rounded border border-slate-800 flex justify-between items-center">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-emerald-400" />
                <span className="text-xs text-emerald-300 font-medium">Conforme Régime Douanier FCR TRE</span>
              </div>

              <div className="text-right font-mono">
                <span className="text-[10px] text-slate-400 uppercase block">Total Rendu Tunis:</span>
                <span className="text-lg font-bold text-emerald-400">{totalPriceEur.toLocaleString()} €</span>
              </div>
            </div>
          </div>
        </div>

        {/* Modal Footer Actions */}
        <div className="p-4 bg-slate-950 border-t border-slate-800 flex items-center justify-between">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 text-xs bg-slate-800 text-slate-300 rounded hover:bg-slate-700 transition-colors"
          >
            Fermer
          </button>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleDownload}
              disabled={downloadSuccess}
              className={`px-3 py-1.5 text-xs font-medium rounded border transition-colors flex items-center gap-1.5 ${
                downloadSuccess
                  ? "bg-emerald-950 text-emerald-400 border-emerald-800 cursor-default"
                  : "bg-slate-800 hover:bg-slate-700 text-slate-200 border-slate-700"
              }`}
            >
              <Download className="w-3.5 h-3.5" />
              {downloadSuccess ? "✓ PDF prêt au téléchargement" : "Télécharger PDF"}
            </button>

            <button
              type="button"
              onClick={onSendToWhatsApp}
              className="px-4 py-1.5 text-xs bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded transition-colors flex items-center gap-1.5 shadow-sm"
            >
              <Send className="w-3.5 h-3.5" />
              Attacher & Envoyer sur WhatsApp
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
