import React from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, UserCheck, MessageSquare, ArrowRight, ShieldAlert, Clock } from "lucide-react";
import { apiClient } from "../../../shared/api/client";

interface HumanAttentionItem {
  id: string;
  customerName: string;
  customerPhone: string;
  lastMessageContent: string;
  handoffReason: string;
  handoffSummary: string;
  mode: string;
  conversationState: string;
  lastMessageAt: string;
}

interface HumanAttentionQueueProps {
  onSelectConversation?: (conversationId: string) => void;
}

export const HumanAttentionQueue: React.FC<HumanAttentionQueueProps> = ({ onSelectConversation }) => {
  const { data: items = [], isLoading, refetch } = useQuery<HumanAttentionItem[]>({
    queryKey: ["human-attention-queue"],
    queryFn: async () => {
      try {
        const res = await apiClient.get<any>("/conversations/human-attention");
        const list = Array.isArray(res.data) ? res.data : res.data?.data || [];
        return list.map((c: any) => ({
          id: c.id,
          customerName: c.customer_name || c.customer_phone_e164 || "Client WhatsApp",
          customerPhone: c.customer_phone_e164 || "+216 -- --- ---",
          lastMessageContent: c.last_message_content || "Message en attente d'intervention",
          handoffReason: c.handoff_reason || "DEMANDE_SUPPORT",
          handoffSummary: c.handoff_summary || "Intervention humaine requise.",
          mode: c.mode || "HUMAN",
          conversationState: c.conversation_state || "HUMAN_ATTENTION",
          lastMessageAt: c.last_message_at || new Date().toISOString(),
        }));
      } catch {
        return [];
      }
    },
    refetchInterval: 3000,
  });

  if (isLoading) {
    return (
      <div className="p-8 text-center text-xs text-slate-500 font-mono">
        Chargement de la file d'attention humaine...
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 text-center text-xs text-slate-400 font-sans space-y-2">
        <UserCheck className="w-8 h-8 text-emerald-400 mx-auto opacity-80" />
        <h4 className="font-semibold text-slate-200">Aucune intervention requise</h4>
        <p className="text-slate-500 max-w-sm mx-auto text-[11px]">
          L'Agent IA 24/7 gère actuellement toutes les conversations WhatsApp sans exception.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3 font-sans">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-400" />
          NEEDS HUMAN ATTENTION ({items.length})
        </h3>
        <button
          onClick={() => refetch()}
          className="text-[11px] text-blue-400 hover:underline font-mono"
        >
          Actualiser
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {items.map((item) => (
          <div
            key={item.id}
            className="bg-slate-900 border border-amber-900/50 hover:border-amber-700/80 rounded-xl p-4 transition-all space-y-3 shadow-lg group"
          >
            <div className="flex items-start justify-between">
              <div>
                <h4 className="font-bold text-slate-100 text-sm">{item.customerName}</h4>
                <p className="text-xs text-slate-400 font-mono">{item.customerPhone}</p>
              </div>
              <span className="px-2 py-0.5 text-[10px] font-mono font-semibold bg-amber-950 text-amber-300 border border-amber-700/60 rounded-full flex items-center gap-1">
                <ShieldAlert className="w-3 h-3 text-amber-400" />
                {item.handoffReason}
              </span>
            </div>

            <div className="bg-slate-950 p-2.5 rounded border border-slate-800 text-xs text-slate-300 space-y-1">
              <span className="text-[10px] text-slate-500 font-mono block">Dernier Message:</span>
              <p className="italic text-slate-200 line-clamp-2">"{item.lastMessageContent}"</p>
            </div>

            {item.handoffSummary && (
              <p className="text-[11px] text-amber-200/90 font-mono bg-amber-950/40 p-2 rounded border border-amber-900/40">
                💡 {item.handoffSummary}
              </p>
            )}

            <div className="flex items-center justify-between pt-1 border-t border-slate-800/80">
              <span className="text-[10px] text-slate-500 font-mono flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {new Date(item.lastMessageAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </span>

              <button
                onClick={() => onSelectConversation?.(item.id)}
                className="px-3 py-1.5 bg-amber-600 hover:bg-amber-500 text-white font-semibold text-xs rounded transition-all flex items-center gap-1.5 shadow-sm group-hover:translate-x-0.5"
              >
                <MessageSquare className="w-3.5 h-3.5" />
                Ouvrir la Conversation
                <ArrowRight className="w-3 h-3" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
