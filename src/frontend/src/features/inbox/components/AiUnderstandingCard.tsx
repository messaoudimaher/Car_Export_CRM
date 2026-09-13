import React from "react";
import { Sparkles, CheckCircle, XCircle, AlertCircle } from "lucide-react";
import { AiUnderstanding } from "../types";

interface AiUnderstandingCardProps {
  understanding: AiUnderstanding;
  onConfirm?: (understandingId: string) => void;
  onReject?: (understandingId: string) => void;
}

export const AiUnderstandingCard: React.FC<AiUnderstandingCardProps> = ({
  understanding,
  onConfirm,
  onReject,
}) => {
  const confidencePercent = Math.round(understanding.confidenceScore * 100);
  const isConfirmed = understanding.status === "CONFIRMED";
  const isRejected = understanding.status === "REJECTED";

  if (isRejected) return null;

  return (
    <div
      className={`rounded-lg p-3.5 my-2 border text-xs shadow-md transition-all ${
        isConfirmed
          ? "bg-slate-900/90 border-emerald-800/80 text-slate-200"
          : "bg-indigo-950/90 border-indigo-700/80 text-indigo-100"
      }`}
    >
      {/* Card Header */}
      <div className="flex items-center justify-between pb-2 border-b border-indigo-800/60 mb-2">
        <div className="flex items-center gap-2">
          <Sparkles className={`w-4 h-4 ${isConfirmed ? "text-emerald-400" : "text-indigo-400 animate-pulse"}`} />
          <span className="font-semibold uppercase tracking-wider text-[11px]">
            {isConfirmed ? "Extraction Validée par Conseiller" : "Extraction IA — Provisoire (Unconfirmed)"}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-indigo-900/80 text-indigo-200 border border-indigo-700/60">
            {confidencePercent}% Confiance
          </span>
          <span className="text-[9px] font-mono text-indigo-300/80">INV-003 HITL</span>
        </div>
      </div>

      {/* Extracted Parameters Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 py-1 mb-3 text-[11px]">
        <div className="bg-indigo-900/40 p-1.5 rounded border border-indigo-800/50">
          <span className="text-[9px] text-indigo-300 block uppercase">Modèle Identifié</span>
          <span className="font-semibold text-slate-100 truncate block">
            {understanding.extractedVehicleModel || "Non spécifié"}
          </span>
        </div>

        <div className="bg-indigo-900/40 p-1.5 rounded border border-indigo-800/50">
          <span className="text-[9px] text-indigo-300 block uppercase">Année Souhaitée</span>
          <span className="font-semibold text-slate-100 font-mono block">
            {understanding.extractedYearMin
              ? `${understanding.extractedYearMin} - ${understanding.extractedYearMax || understanding.extractedYearMin}`
              : "—"}
          </span>
        </div>

        <div className="bg-indigo-900/40 p-1.5 rounded border border-indigo-800/50">
          <span className="text-[9px] text-indigo-300 block uppercase">Budget Détecté</span>
          <span className="font-semibold text-emerald-300 font-mono block">
            {understanding.extractedBudgetMinEur
              ? `${understanding.extractedBudgetMinEur.toLocaleString()} € - ${understanding.extractedBudgetMaxEur?.toLocaleString()} €`
              : "—"}
          </span>
        </div>

        <div className="bg-indigo-900/40 p-1.5 rounded border border-indigo-800/50">
          <span className="text-[9px] text-indigo-300 block uppercase">Régime Douanier</span>
          <span className="font-semibold text-indigo-200 font-mono block">
            {understanding.extractedFcrEligible ? "FCR Éligible (TRE)" : "Standard"}
          </span>
        </div>
      </div>

      {/* Action Buttons Toolbar */}
      {!isConfirmed && (
        <div className="flex items-center justify-between pt-2 border-t border-indigo-800/60">
          <div className="flex items-center gap-1.5 text-[10px] text-indigo-300 italic">
            <AlertCircle className="w-3 h-3 text-indigo-400" />
            <span>Action humaine requise pour mettre à jour la fiche lead</span>
          </div>

          <div className="flex items-center gap-2">
            {onReject && (
              <button
                type="button"
                onClick={() => onReject(understanding.id)}
                className="px-2.5 py-1 text-[11px] bg-slate-900 hover:bg-slate-800 text-slate-300 rounded border border-slate-700 transition-colors flex items-center gap-1"
              >
                <XCircle className="w-3 h-3 text-slate-400" />
                Ignorer
              </button>
            )}

            {onConfirm && (
              <button
                type="button"
                onClick={() => onConfirm(understanding.id)}
                className="px-3 py-1 text-[11px] bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded transition-colors flex items-center gap-1.5 shadow-sm"
              >
                <CheckCircle className="w-3.5 h-3.5" />
                Confirmer & Appliquer au Lead
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
