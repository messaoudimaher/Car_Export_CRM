import React, { useState, useEffect, useRef } from "react";
import { ThreadList } from "./ThreadList";
import { ChatHistory } from "./ChatHistory";
import { CustomerSidebar } from "./CustomerSidebar";
import { QuotationBuilder } from "../../quotes/components/QuotationBuilder";
import { useThreads, useThreadMessages, useSendMessage, useTakeoverConversation, useResumeAiConversation } from "../api/inboxApi";
import { InboxFilter, ConversationThread } from "../types";

export const InboxWorkspace: React.FC = () => {
  const [filter, setFilter] = useState<InboxFilter>({ status: "ALL" });
  const [activeThreadId, setActiveThreadId] = useState<string | undefined>();
  const [isQuoteBuilderOpen, setIsQuoteBuilderOpen] = useState(false);
  const [showSidebarMobile, setShowSidebarMobile] = useState(false);
  const [showShortcutHelp, setShowShortcutHelp] = useState(false);
  const replyInputRef = useRef<HTMLTextAreaElement | null>(null);

  const { data: threads = [], isLoading: isLoadingThreads } = useThreads(filter);

  // Default select first thread if none active
  useEffect(() => {
    if (!activeThreadId && threads.length > 0) {
      setActiveThreadId(threads[0].id);
    }
  }, [threads, activeThreadId]);

  const activeThread = threads.find((t: ConversationThread) => t.id === activeThreadId) || threads[0];

  const { data: messages = [], isLoading: isLoadingMessages } = useThreadMessages(activeThread?.id);
  const sendMessageMutation = useSendMessage();
  const takeoverMutation = useTakeoverConversation();
  const resumeAiMutation = useResumeAiConversation();

  const handleSendMessage = async (content: string) => {
    if (!activeThread) return;
    await sendMessageMutation.mutateAsync({ threadId: activeThread.id, content });
  };

  const handleTakeover = async () => {
    if (!activeThread) return;
    await takeoverMutation.mutateAsync(activeThread.id);
  };

  const handleResumeAi = async () => {
    if (!activeThread) return;
    await resumeAiMutation.mutateAsync(activeThread.id);
  };

  const handleSendQuoteToChat = async (_pdfUrl: string, summaryText: string) => {
    if (!activeThread) return;
    await sendMessageMutation.mutateAsync({ threadId: activeThread.id, content: summaryText });
  };

  // Keyboard navigation shortcuts: j/k thread selection, r focus reply, Esc blur
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const targetTag = target?.tagName?.toLowerCase();
      const isEditable = target?.isContentEditable;

      // Ignore key shortcuts when typing inside an input, textarea, select, or editable element
      if (targetTag === "input" || targetTag === "textarea" || targetTag === "select" || isEditable) {
        if (e.key === "Escape") {
          target.blur();
        }
        return;
      }

      if (e.key === "j" || e.key === "J") {
        e.preventDefault();
        if (threads.length === 0) return;
        const currentIndex = threads.findIndex((t: ConversationThread) => t.id === activeThreadId);
        const nextIndex = currentIndex < threads.length - 1 ? currentIndex + 1 : 0;
        setActiveThreadId(threads[nextIndex].id);
      } else if (e.key === "k" || e.key === "K") {
        e.preventDefault();
        if (threads.length === 0) return;
        const currentIndex = threads.findIndex((t: ConversationThread) => t.id === activeThreadId);
        const prevIndex = currentIndex > 0 ? currentIndex - 1 : threads.length - 1;
        setActiveThreadId(threads[prevIndex].id);
      } else if (e.key === "r" || e.key === "R") {
        e.preventDefault();
        replyInputRef.current?.focus();
      } else if (e.key === "?") {
        e.preventDefault();
        setShowShortcutHelp((prev) => !prev);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [threads, activeThreadId]);

  return (
    <div className="flex-1 flex h-[calc(100vh-3.5rem)] w-full overflow-hidden bg-slate-950 font-sans text-slate-100 relative">
      {/* Pane 1: Left Thread List (320px) */}
      <div className="w-full md:w-80 flex-shrink-0 border-r border-slate-800 flex flex-col">
        <ThreadList
          threads={threads}
          activeThreadId={activeThread?.id}
          onSelectThread={setActiveThreadId}
          filter={filter}
          onFilterChange={setFilter}
          isLoading={isLoadingThreads}
        />
      </div>

      {/* Pane 2: Center Chat History Timeline (flex-1) */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile / Responsive Header Toolbar */}
        <div className="xl:hidden bg-slate-900 border-b border-slate-800 p-2 flex items-center justify-between text-xs">
          <button
            onClick={() => setShowShortcutHelp(true)}
            className="px-2 py-1 bg-slate-800 text-slate-300 rounded text-[11px] font-mono border border-slate-700"
          >
            ⌨️ Raccourcis (?)
          </button>
          <button
            onClick={() => setShowSidebarMobile((prev) => !prev)}
            className="px-2.5 py-1 bg-blue-600/30 text-blue-300 rounded text-[11px] font-medium border border-blue-500/50"
          >
            {showSidebarMobile ? "Masquer Profil" : "Voir Profil Client (380px)"}
          </button>
        </div>

        <ChatHistory
          thread={activeThread}
          messages={messages}
          onSendMessage={handleSendMessage}
          isLoading={isLoadingMessages}
          replyInputRef={replyInputRef}
        />
      </div>

      {/* Pane 3: Right Customer & Sourcing Sidebar (380px desktop, drawer on mobile) */}
      <div className={`${showSidebarMobile ? "block" : "hidden"} xl:block w-[380px] flex-shrink-0 border-l border-slate-800`}>
        <CustomerSidebar
          customer={activeThread?.customer}
          lead={activeThread?.lead}
          mode={activeThread?.mode}
          onTakeover={handleTakeover}
          onResumeAi={handleResumeAi}
          onOpenQuoteBuilder={() => setIsQuoteBuilderOpen(true)}
        />
      </div>

      {/* Visible Keyboard Shortcut Help Modal */}
      {showShortcutHelp && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 w-full max-w-sm text-xs font-sans space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <h3 className="font-bold text-slate-100 flex items-center gap-2">⌨️ Raccourcis Clavier Operational Inbox</h3>
              <button onClick={() => setShowShortcutHelp(false)} className="text-slate-400 hover:text-slate-200">
                ✕
              </button>
            </div>

            <ul className="space-y-2 font-mono text-[11px] text-slate-300">
              <li className="flex justify-between border-b border-slate-800/60 pb-1">
                <span>Fil suivant</span>
                <kbd className="px-1.5 py-0.5 bg-slate-800 rounded text-blue-400">j</kbd>
              </li>
              <li className="flex justify-between border-b border-slate-800/60 pb-1">
                <span>Fil précédent</span>
                <kbd className="px-1.5 py-0.5 bg-slate-800 rounded text-blue-400">k</kbd>
              </li>
              <li className="flex justify-between border-b border-slate-800/60 pb-1">
                <span>Focaliser réponse</span>
                <kbd className="px-1.5 py-0.5 bg-slate-800 rounded text-blue-400">r</kbd>
              </li>
              <li className="flex justify-between">
                <span>Fermer / Dé-focaliser</span>
                <kbd className="px-1.5 py-0.5 bg-slate-800 rounded text-blue-400">Esc</kbd>
              </li>
            </ul>

            <p className="text-[10px] text-slate-400 font-sans italic border-t border-slate-800 pt-2">
              Note: Les raccourcis j/k/r sont automatiquement désactivés lorsque vous saisissez du texte dans un champ d'édition.
            </p>

            <button
              onClick={() => setShowShortcutHelp(false)}
              className="w-full py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded font-medium text-xs transition-colors"
            >
              Compris
            </button>
          </div>
        </div>
      )}

      {/* Quotation Builder Drawer Modal */}
      {activeThread && (
        <QuotationBuilder
          isOpen={isQuoteBuilderOpen}
          onClose={() => setIsQuoteBuilderOpen(false)}
          customerName={activeThread.customerName}
          customerPhone={activeThread.customerPhone}
          onSendQuoteToChat={handleSendQuoteToChat}
        />
      )}
    </div>
  );
};
