import React, { useState } from "react";
import { X, FileText, Calculator, ShieldCheck, Eye, RefreshCw, AlertTriangle } from "lucide-react";
import { QuotePdfPreviewModal } from "./QuotePdfPreviewModal";

interface QuotationBuilderProps {
  customerName: string;
  customerPhone: string;
  isOpen: boolean;
  onClose: () => void;
  onSendQuoteToChat?: (pdfUrl: string, summaryText: string) => void;
}

export type VatRegime = "NETTO_EXPORT" | "BRUTTO_MARGIN";

export const QuotationBuilder: React.FC<QuotationBuilderProps> = ({
  customerName,
  customerPhone,
  isOpen,
  onClose,
  onSendQuoteToChat,
}) => {
  const [vehicleModel, setVehicleModel] = useState("BMW X5 xDrive30d M Sport");
  const [year, setYear] = useState(2022);
  const [mileageKm, setMileageKm] = useState(45000);
  const [vin, setVin] = useState("WBA1234567890ABCD");

  const [priceExclVatEur, setPriceExclVatEur] = useState(45000);
  const [discountPercent, setDiscountPercent] = useState(0);
  const [vatRegime, setVatRegime] = useState<VatRegime>("NETTO_EXPORT");
  const [transportFeeEur, setTransportFeeEur] = useState(1200);
  const [serviceFeeEur, setServiceFeeEur] = useState(800);

  const [isPreviewOpen, setIsPreviewOpen] = useState(false);

  if (!isOpen) return null;

  // Exact Deterministic Financial Calculations (BR-005, BR-006, BR-015)
  const discountedBasePriceEur = Math.round(priceExclVatEur * (1 - discountPercent / 100));
  const vatAmountEur = vatRegime === "NETTO_EXPORT" ? 0 : Math.round(discountedBasePriceEur * 0.19);
  const subtotalEur = discountedBasePriceEur + vatAmountEur;
  const totalExportPriceEur = subtotalEur + transportFeeEur + serviceFeeEur;
  const estimatedTndAmount = Math.round(totalExportPriceEur * 3.35);

  const handleGeneratePdf = () => {
    setIsPreviewOpen(true);
  };

  const handleSendToChat = () => {
    const summaryText = `📄 *DEVIS OFFICIEL FCR CAR-EXPORT-CRM*\n*Client*: ${customerName}\n*Véhicule*: ${vehicleModel} (${year})\n*Régime TVA*: ${vatRegime === "NETTO_EXPORT" ? "Netto Export (TVA 0%)" : "Brutto Marge"}\n*Prix Total Export*: ${totalExportPriceEur.toLocaleString()} € (~${estimatedTndAmount.toLocaleString()} TND)\n\n*Notice Douane*: Éligible Exonération FCR TRE (Taxe réduite 25%).`;
    if (onSendQuoteToChat) {
      onSendQuoteToChat("https://api.carexport.com/v1/documents/demo_quote_fcr.pdf", summaryText);
    }
    setIsPreviewOpen(false);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex justify-end animate-fade-in">
      <div className="w-[520px] bg-slate-900 border-l border-slate-800 h-full flex flex-col shadow-2xl font-sans text-slate-100 select-none">
        {/* Drawer Header */}
        <div className="p-4 bg-slate-950 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Calculator className="w-5 h-5 text-blue-400" />
            <div>
              <h2 className="text-sm font-bold text-slate-100">Générateur de Devis FCR</h2>
              <p className="text-[10px] text-slate-400 font-mono">
                Client: {customerName} ({customerPhone}) • <span className="text-amber-400 font-sans">Aperçu Client (Backend Authoritative)</span>
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-slate-200 rounded hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Drawer Body - Form Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Section 1: Vehicle Info */}
          <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-800 space-y-3">
            <h3 className="text-xs font-semibold text-blue-400 uppercase tracking-wider flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5" />
              1. Spécifications du Véhicule
            </h3>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <label className="text-[10px] text-slate-400 block mb-1">Modèle / Marque</label>
                <input
                  type="text"
                  value={vehicleModel}
                  onChange={(e) => setVehicleModel(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="text-[10px] text-slate-400 block mb-1">Numéro Châssis (VIN)</label>
                <input
                  type="text"
                  value={vin}
                  onChange={(e) => setVin(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100 font-mono focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="text-[10px] text-slate-400 block mb-1">Année Mise en Circulation</label>
                <input
                  type="number"
                  value={year}
                  onChange={(e) => setYear(Number(e.target.value))}
                  className="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100 font-mono focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="text-[10px] text-slate-400 block mb-1">Kilométrage (km)</label>
                <input
                  type="number"
                  value={mileageKm}
                  onChange={(e) => setMileageKm(Number(e.target.value))}
                  className="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100 font-mono focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
          </div>

          {/* Section 2: Pricing & VAT Regime */}
          <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-800 space-y-3">
            <h3 className="text-xs font-semibold text-emerald-400 uppercase tracking-wider flex items-center gap-1.5">
              <RefreshCw className="w-3.5 h-3.5" />
              2. Régime Fiscal & Tarification HT/TTC
            </h3>

            <div>
              <label className="text-[10px] text-slate-400 block mb-1">Sélection Régime TVA Allemagne</label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setVatRegime("NETTO_EXPORT")}
                  className={`p-2 rounded border text-xs text-left font-medium transition-all ${
                    vatRegime === "NETTO_EXPORT"
                      ? "bg-emerald-950/80 border-emerald-500 text-emerald-300"
                      : "bg-slate-900 border-slate-800 text-slate-400 hover:border-slate-700"
                  }`}
                >
                  <div className="font-bold text-slate-100">Netto Export (TVA 0%)</div>
                  <div className="text-[10px] opacity-80 mt-0.5">Vente Hors Taxe déductible pour export hors UE / FCR.</div>
                </button>

                <button
                  type="button"
                  onClick={() => setVatRegime("BRUTTO_MARGIN")}
                  className={`p-2 rounded border text-xs text-left font-medium transition-all ${
                    vatRegime === "BRUTTO_MARGIN"
                      ? "bg-blue-950/80 border-blue-500 text-blue-300"
                      : "bg-slate-900 border-slate-800 text-slate-400 hover:border-slate-700"
                  }`}
                >
                  <div className="font-bold text-slate-100">Brutto Marge (§25a)</div>
                  <div className="text-[10px] opacity-80 mt-0.5">TVA sur Marge non déductible (Occasion).</div>
                </button>
              </div>
            </div>

            <div className="grid grid-cols-4 gap-2 text-xs pt-1">
              <div>
                <label className="text-[10px] text-slate-400 block mb-1">Prix Achat HT (€)</label>
                <input
                  type="number"
                  value={priceExclVatEur}
                  onChange={(e) => setPriceExclVatEur(Number(e.target.value))}
                  className="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100 font-mono focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label htmlFor="discount-input" className="text-[10px] text-slate-400 block mb-1">Remise Remise (%)</label>
                <input
                  id="discount-input"
                  type="number"
                  min={0}
                  max={50}
                  value={discountPercent}
                  onChange={(e) => setDiscountPercent(Number(e.target.value))}
                  className="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100 font-mono focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="text-[10px] text-slate-400 block mb-1">Transport Maritime (€)</label>
                <input
                  type="number"
                  value={transportFeeEur}
                  onChange={(e) => setTransportFeeEur(Number(e.target.value))}
                  className="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100 font-mono focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="text-[10px] text-slate-400 block mb-1">Frais Dossier Export (€)</label>
                <input
                  type="number"
                  value={serviceFeeEur}
                  onChange={(e) => setServiceFeeEur(Number(e.target.value))}
                  className="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100 font-mono focus:outline-none focus:border-emerald-500"
                />
              </div>
            </div>

            {/* BR-015 Manager Approval Warning */}
            {discountPercent > 5 && (
              <div className="p-2 bg-amber-950/80 border border-amber-700/80 rounded text-amber-200 text-[11px] flex items-center gap-2 font-mono">
                <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
                <span>Attention (BR-015): Remise de {discountPercent}% &gt; 5%. Soumission réservée à la validation d'un Manager.</span>
              </div>
            )}
          </div>

          {/* Section 3: Financial Summary Breakdown */}
          <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-2 text-xs">
            <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider mb-2">
              3. Décomposition du Prix Total Export
            </h3>

            <div className="flex justify-between text-slate-400">
              <span>Prix Véhicule HT:</span>
              <span className="font-mono text-slate-200">{priceExclVatEur.toLocaleString()} €</span>
            </div>

            <div className="flex justify-between text-slate-400">
              <span>Montant TVA Allemagne:</span>
              <span className="font-mono text-slate-200">{vatAmountEur.toLocaleString()} €</span>
            </div>

            <div className="flex justify-between text-slate-400">
              <span>Frais Transport & Service Export:</span>
              <span className="font-mono text-slate-200">{(transportFeeEur + serviceFeeEur).toLocaleString()} €</span>
            </div>

            <div className="pt-2 border-t border-slate-800 flex justify-between items-center text-sm font-bold">
              <span className="text-slate-100">Prix Total Export Rendu Tunis:</span>
              <span className="font-mono text-emerald-400 text-base">{totalExportPriceEur.toLocaleString()} €</span>
            </div>

            <div className="text-[10px] text-slate-500 flex justify-between font-mono">
              <span>Estimation Dinar Tunisien (~3.35 TND/EUR):</span>
              <span>{estimatedTndAmount.toLocaleString()} TND</span>
            </div>

            {/* FCR Tax Exemption Notice (BR-006) */}
            <div className="mt-3 p-2 bg-emerald-950/40 border border-emerald-800/60 rounded text-[11px] text-emerald-300 flex items-start gap-1.5">
              <ShieldCheck className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold block">Notice Exonération Douane FCR TRE:</span>
                <p className="text-[10px] leading-relaxed opacity-90">
                  Client éligible au privilège fiscal FCR. Droit de consommation réduit à 25% au lieu du régime commun 100%+.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Drawer Footer Actions */}
        <div className="p-4 bg-slate-950 border-t border-slate-800 flex items-center justify-between">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 text-xs bg-slate-800 text-slate-300 rounded hover:bg-slate-700 transition-colors"
          >
            Annuler
          </button>

          <button
            type="button"
            onClick={handleGeneratePdf}
            className="px-4 py-2 text-xs bg-blue-600 hover:bg-blue-500 text-white font-medium rounded transition-colors flex items-center gap-1.5 shadow-sm"
          >
            <Eye className="w-4 h-4" />
            Générer & Aperçu PDF Pre-signed
          </button>
        </div>
      </div>

      {/* PDF Preview Modal */}
      <QuotePdfPreviewModal
        isOpen={isPreviewOpen}
        onClose={() => setIsPreviewOpen(false)}
        customerName={customerName}
        totalPriceEur={totalExportPriceEur}
        onSendToWhatsApp={handleSendToChat}
      />
    </div>
  );
};
