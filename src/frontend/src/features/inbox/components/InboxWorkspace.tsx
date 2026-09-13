import React, { useState, useEffect, useRef } from "react";
import { ThreadList } from "./ThreadList";
import { ChatHistory } from "./ChatHistory";
import { CustomerSidebar } from "./CustomerSidebar";
import { useThreads, useThreadMessages, useSendMessage } from "../api/inboxApi";
import { InboxFilter } from "../types";

export const InboxWorkspace: React.FC = () => {
  const [filter, setFilter] = useState<InboxFilter>({ status: "ALL" });
  const [activeThreadId, setActiveThreadId] = useState<string | undefined>();
  const replyInputRef = useRef<HTMLTextAreaElement | null>(null);

  const { data: threads = [], isLoading: isLoadingThreads } = useThreads(filter);

  // Default select first thread if none active
  useEffect(() => {
    if (!activeThreadId && threads.length > 0) {
      setActiveThreadId(threads[0].id);
    }
  }, [threads, activeThreadId]);

  const activeThread = threads.find((t) => t.id === activeThreadId) || threads[0];

  const { data: messages = [], isLoading: isLoadingMessages } = useThreadMessages(activeThread?.id);
  const sendMessageMutation = useSendMessage();

  const handleSendMessage = async (content: string) => {
    if (!activeThread) return;
    await sendMessageMutation.mutateAsync({ threadId: activeThread.id, content });
  };

  // Keyboard navigation shortcuts: j/k thread selection, r focus reply, Esc blur
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore key shortcuts when typing inside an input or textarea
      const targetTag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      if (targetTag === "input" || targetTag === "textarea") {
        if (e.key === "Escape") {
          (e.target as HTMLElement).blur();
        }
        return;
      }

      if (e.key === "j" || e.key === "J") {
        e.preventDefault();
        if (threads.length === 0) return;
        const currentIndex = threads.findIndex((t) => t.id === activeThreadId);
        const nextIndex = currentIndex < threads.length - 1 ? currentIndex + 1 : 0;
        setActiveThreadId(threads[nextIndex].id);
      } else if (e.key === "k" || e.key === "K") {
        e.preventDefault();
        if (threads.length === 0) return;
        const currentIndex = threads.findIndex((t) => t.id === activeThreadId);
        const prevIndex = currentIndex > 0 ? currentIndex - 1 : threads.length - 1;
        setActiveThreadId(threads[prevIndex].id);
      } else if (e.key === "r" || e.key === "R") {
        e.preventDefault();
        replyInputRef.current?.focus();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [threads, activeThreadId]);

  return (
    <div className="flex-1 flex h-[calc(100vh-3.5rem)] w-full overflow-hidden bg-slate-950 font-sans text-slate-100">
      {/* Pane 1: Left Thread List (320px) */}
      <ThreadList
        threads={threads}
        activeThreadId={activeThread?.id}
        onSelectThread={setActiveThreadId}
        filter={filter}
        onFilterChange={setFilter}
        isLoading={isLoadingThreads}
      />

      {/* Pane 2: Center Chat History Timeline (flex-1) */}
      <ChatHistory
        thread={activeThread}
        messages={messages}
        onSendMessage={handleSendMessage}
        isLoading={isLoadingMessages}
        replyInputRef={replyInputRef}
      />

      {/* Pane 3: Right Customer & Sourcing Sidebar (380px) */}
      <CustomerSidebar
        customer={activeThread?.customer}
        lead={activeThread?.lead}
      />
    </div>
  );
};
