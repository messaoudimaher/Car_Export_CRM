import React from "react";
import { Bot, Send, Edit3, XCircle, Info } from "lucide-react";
import { AiSuggestion } from "../types";

interface AiSuggestionCardProps {
  suggestion: AiSuggestion;
  onApproveAndSend?: (suggestion: AiSuggestion) => void;
  onInsertIntoEditor?: (text: string) => void;
  onReject?: (suggestionId: string) => void;
}

export const AiSuggestionCard: React.FC<AiSuggestionCardProps> = ({
  suggestion,
  onApproveAndSend,
  onInsertIntoEditor,
  onReject,
}) => {
  const confidencePercent = Math.round(suggestion.confidenceScore * 100);
  const isApproved = suggestion.status === "APPROVED";
  const isRejected = suggestion.status === "REJECTED";

  if (isRejected) return null;

  return (
    <div
      className={`rounded-lg p-3.5 my-2 border text-xs shadow-md transition-all ${
        isApproved
          ? "bg-slate-900/90 border-emerald-800/80 text-slate-200"
          : "bg-amber-950/90 border-amber-700/80 text-amber-100"
      }`}
    >
      {/* Card Header */}
      <div className="flex items-center justify-between pb-2 border-b border-amber-800/60 mb-2">
        <div className="flex items-center gap-2">
          <Bot className={`w-4 h-4 ${isApproved ? "text-emerald-400" : "text-amber-400 animate-pulse"}`} />
          <span className="font-semibold uppercase tracking-wider text-[11px]">
            {isApproved ? "Réponse IA Envoyée avec Succès" : "Suggestion de Réponse IA — Non Envoyée"}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-amber-900/80 text-amber-200 border border-amber-700/60">
            {confidencePercent}% Confiance
          </span>
          <span className="text-[9px] font-mono text-amber-300/80">ADR 0012 HITL</span>
        </div>
      </div>

      {/* Suggested Text Body */}
      <div className="bg-amber-900/30 p-2.5 rounded border border-amber-800/50 mb-3 space-y-1">
        <p className="text-slate-100 font-sans leading-relaxed text-xs">{suggestion.suggestedText}</p>
        {suggestion.reasoningSnippet && (
          <div className="flex items-center gap-1 text-[10px] text-amber-300/80 pt-1 font-mono border-t border-amber-800/40">
            <Info className="w-3 h-3 text-amber-400 flex-shrink-0" />
            <span>Justification: {suggestion.reasoningSnippet}</span>
          </div>
        )}
      </div>

      {/* Action Buttons Toolbar */}
      {!isApproved && (
        <div className="flex items-center justify-between pt-2 border-t border-amber-800/60">
          <div className="flex items-center gap-1 text-[10px] text-amber-300 italic">
            <span>Aucun envoi automatique vers le client (Loi Non-Authoritative INV-003)</span>
          </div>

          <div className="flex items-center gap-2">
            {onReject && (
              <button
                type="button"
                onClick={() => onReject(suggestion.id)}
                className="px-2.5 py-1 text-[11px] bg-slate-900 hover:bg-slate-800 text-slate-300 rounded border border-slate-700 transition-colors flex items-center gap-1"
              >
                <XCircle className="w-3 h-3 text-slate-400" />
                Ignorer
              </button>
            )}

            {onInsertIntoEditor && (
              <button
                type="button"
                onClick={() => onInsertIntoEditor(suggestion.suggestedText)}
                className="px-2.5 py-1 text-[11px] bg-amber-900/80 hover:bg-amber-800 text-amber-200 rounded border border-amber-700/80 transition-colors flex items-center gap-1"
              >
                <Edit3 className="w-3.5 h-3.5" />
                Insérer dans l'Éditeur
              </button>
            )}

            {onApproveAndSend && (
              <button
                type="button"
                onClick={() => onApproveAndSend(suggestion)}
                className="px-3 py-1 text-[11px] bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded transition-colors flex items-center gap-1.5 shadow-sm"
              >
                <Send className="w-3.5 h-3.5" />
                Approuver & Envoyer WhatsApp
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
