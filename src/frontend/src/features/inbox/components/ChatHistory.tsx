import React, { useState, useRef, useEffect } from "react";
import { Send, CheckCheck, Check, Clock, ShieldCheck, PhoneCall, Paperclip, Sparkles, ShieldAlert } from "lucide-react";
import { ChatMessage, ConversationThread } from "../types";
import { AiUnderstandingCard } from "./AiUnderstandingCard";

interface ChatHistoryProps {
  thread?: ConversationThread;
  messages: ChatMessage[];
  onSendMessage: (content: string) => Promise<void>;
  isLoading?: boolean;
  replyInputRef?: React.RefObject<HTMLTextAreaElement | null>;
}

export const ChatHistory: React.FC<ChatHistoryProps> = ({
  thread,
  messages,
  onSendMessage,
  isLoading,
  replyInputRef,
}) => {
  const [content, setContent] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [activeUnderstanding, setActiveUnderstanding] = useState(thread?.activeAiUnderstanding);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setActiveUnderstanding(thread?.activeAiUnderstanding);
  }, [thread]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, activeUnderstanding]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = content.trim();
    if (!trimmed || isSubmitting) return;

    // Clear content BEFORE awaiting to prevent React batching/double-submission issues
    setContent("");
    try {
      setIsSubmitting(true);
      await onSendMessage(trimmed);
    } catch {
      // Restore content on failure so agent doesn't lose their message
      setContent(trimmed);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleConfirmUnderstanding = (_id: string) => {
    if (activeUnderstanding) {
      // Show confirmed state briefly, then auto-dismiss after 2.5s (Bug #4 fix)
      setActiveUnderstanding({ ...activeUnderstanding, status: "CONFIRMED" });
      setTimeout(() => setActiveUnderstanding(undefined), 2500);
    }
  };

  if (!thread) {
    return (
      <main className="flex-1 flex flex-col items-center justify-center bg-slate-950 text-slate-500 p-8 select-none">
        <Sparkles className="w-12 h-12 text-slate-700 mb-3 animate-pulse" />
        <h3 className="text-sm font-semibold text-slate-300">Aucune conversation sélectionnée</h3>
        <p className="text-xs text-slate-500 mt-1">
          Sélectionnez un fil de discussion dans la liste de gauche (raccourcis <kbd className="px-1 py-0.5 bg-slate-800 rounded">j</kbd>/<kbd className="px-1 py-0.5 bg-slate-800 rounded">k</kbd>).
        </p>
      </main>
    );
  }

  return (
    <main className="flex-1 flex flex-col bg-slate-950 h-full overflow-hidden">
      {/* Conversation Header */}
      <header className="p-3 bg-slate-900 border-b border-slate-800 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-blue-600/20 border border-blue-500/40 flex items-center justify-center text-blue-400 font-bold text-sm">
            {thread.customerName.charAt(0)}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-slate-100">{thread.customerName}</h3>
              <span className="text-[10px] bg-slate-800 text-slate-300 px-1.5 py-0.2 rounded font-mono">
                {thread.channel}
              </span>
            </div>
            <div className="flex items-center gap-2 text-[11px] text-slate-400 font-mono">
              <PhoneCall className="w-3 h-3 text-slate-500" />
              <span>{thread.customerPhone}</span>
              <span className="text-slate-600">•</span>
              <span className="text-blue-400">{thread.assignedAgentName || "Non attribué"}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[11px] text-emerald-400 bg-emerald-950/60 border border-emerald-800/60 px-2 py-0.5 rounded flex items-center gap-1 font-mono">
            <ShieldCheck className="w-3 h-3" />
            WhatsApp Official API
          </span>
        </div>
      </header>

      {/* Chat Messages Timeline & AI HITL Cards */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-[radial-gradient(#1e293b_1px,transparent_1px)] [background-size:16px_16px]">
        {isLoading ? (
          <div className="text-center text-xs text-slate-500 py-8">Chargement de l'historique...</div>
        ) : messages.length === 0 ? (
          <div className="text-center text-xs text-slate-500 py-8">Aucun message dans ce fil.</div>
        ) : (
          messages.map((msg) => {
            const isInbound = msg.direction === "INBOUND";
            const formattedTime = new Date(msg.timestamp).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            });

            return (
              <div key={msg.id} className={`flex flex-col ${isInbound ? "items-start" : "items-end"}`}>
                <div
                  className={`max-w-[75%] rounded-lg p-3 text-xs leading-relaxed ${
                    isInbound
                      ? "bg-slate-900 border border-slate-800 text-slate-200 shadow-sm"
                      : "bg-blue-950/80 border border-blue-800/80 text-blue-100 shadow-sm"
                  }`}
                >
                  <div className="flex items-center justify-between text-[10px] text-slate-400 mb-1 border-b border-slate-800/40 pb-1 gap-3 font-mono">
                    <span className="font-semibold text-slate-300 flex items-center gap-1">
                      {msg.senderName || thread.customerName}
                      {isInbound && (
                        <span className="text-[9px] text-slate-500 bg-slate-950 px-1 py-0.2 rounded border border-slate-800 flex items-center gap-0.5">
                          <ShieldAlert className="w-2.5 h-2.5 text-amber-500" />
                          &lt;untrusted_user_message&gt;
                        </span>
                      )}
                    </span>
                    <span>{formattedTime}</span>
                  </div>

                  <p className="whitespace-pre-wrap font-sans">{msg.content}</p>

                  {!isInbound && (
                    <div className="mt-1 flex items-center justify-end gap-1 text-[10px] text-blue-300 font-mono">
                      <span>{msg.status}</span>
                      {msg.status === "READ" ? (
                        <CheckCheck className="w-3.5 h-3.5 text-blue-400" />
                      ) : msg.status === "DELIVERED" ? (
                        <CheckCheck className="w-3.5 h-3.5 text-slate-400" />
                      ) : (
                        <Check className="w-3.5 h-3.5 text-slate-400" />
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}

        {/* Tier 2: Provisional AI Extraction Card (Indigo) */}
        {activeUnderstanding && (
          <AiUnderstandingCard
            understanding={activeUnderstanding}
            onConfirm={handleConfirmUnderstanding}
            onReject={() => setActiveUnderstanding(undefined)}
          />
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Reply Input Box Drawer */}
      <div className="p-3 bg-slate-900 border-t border-slate-800 flex-shrink-0">
        <form onSubmit={handleSubmit} className="flex flex-col gap-2">
          <div className="relative">
            <textarea
              ref={replyInputRef}
              rows={2}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Répondre sur WhatsApp... (Touche 'r' pour cibler, Enter pour envoyer)"
              className="w-full bg-slate-950 border border-slate-700/80 rounded p-2.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 font-sans resize-none"
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <button
                type="button"
                className="px-2 py-1 text-[11px] bg-slate-800 text-slate-300 rounded border border-slate-700/60 hover:bg-slate-700 transition-colors flex items-center gap-1"
              >
                <Paperclip className="w-3 h-3 text-slate-400" />
                Pièce jointe
              </button>
              <button
                type="button"
                className="px-2 py-1 text-[11px] bg-slate-800 text-slate-300 rounded border border-slate-700/60 hover:bg-slate-700 transition-colors flex items-center gap-1"
              >
                <Clock className="w-3 h-3 text-slate-400" />
                Modèle Devis
              </button>
            </div>

            <button
              type="submit"
              disabled={!content.trim() || isSubmitting}
              className="px-4 py-1.5 text-xs bg-blue-600 text-white rounded font-medium hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5"
            >
              <Send className="w-3.5 h-3.5" />
              {isSubmitting ? "Envoi..." : "Envoyer Réponse"}
            </button>
          </div>
        </form>
      </div>
    </main>
  );
};

