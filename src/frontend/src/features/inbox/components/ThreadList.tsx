import React from "react";
import { Search, MessageSquare, UserCheck, ShieldAlert, CheckCircle2 } from "lucide-react";
import { ConversationThread, InboxFilter } from "../types";

interface ThreadListProps {
  threads: ConversationThread[];
  activeThreadId?: string;
  onSelectThread: (threadId: string) => void;
  filter: InboxFilter;
  onFilterChange: (filter: InboxFilter) => void;
  isLoading?: boolean;
}

export const ThreadList: React.FC<ThreadListProps> = ({
  threads,
  activeThreadId,
  onSelectThread,
  filter,
  onFilterChange,
  isLoading,
}) => {
  const tabs: Array<{ id: InboxFilter["status"]; label: string }> = [
    { id: "ALL", label: "Tous" },
    { id: "MINE", label: "Mes fil" },
    { id: "UNASSIGNED", label: "Non attribué" },
    { id: "CLOSED", label: "Fermés" },
  ];

  return (
    <aside className="w-80 flex-shrink-0 flex flex-col bg-slate-900 border-r border-slate-800 h-full overflow-hidden select-none">
      {/* Search Header */}
      <div className="p-3 border-b border-slate-800 flex flex-col gap-2 bg-slate-950/40">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <MessageSquare className="w-4 h-4 text-blue-400" />
            <h2 className="text-sm font-semibold text-slate-100 uppercase tracking-wider">Conversations</h2>
          </div>
          <span className="text-[10px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded font-mono">
            {threads.length} fils
          </span>
        </div>

        {/* Search Input */}
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-400" />
          <input
            type="text"
            placeholder="Rechercher nom, téléphone..."
            value={filter.searchQuery || ""}
            onChange={(e) => onFilterChange({ ...filter, searchQuery: e.target.value })}
            className="w-full bg-slate-950 border border-slate-700/80 rounded text-xs text-slate-200 pl-8 pr-3 py-1.5 placeholder-slate-500 focus:outline-none focus:border-blue-500 font-sans"
          />
        </div>

        {/* Filter Tabs */}
        <div className="flex gap-1 pt-1 overflow-x-auto no-scrollbar">
          {tabs.map((tab) => {
            const isActive = (filter.status || "ALL") === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => onFilterChange({ ...filter, status: tab.id })}
                className={`px-2 py-1 rounded text-[11px] font-medium whitespace-nowrap transition-colors ${
                  isActive
                    ? "bg-blue-600/30 text-blue-300 border border-blue-500/50"
                    : "bg-slate-800/60 text-slate-400 hover:text-slate-200 border border-transparent"
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Thread Items List */}
      <div className="flex-1 overflow-y-auto divide-y divide-slate-800/60">
        {isLoading ? (
          <div className="p-4 text-center text-xs text-slate-500 animate-pulse">Chargement des conversations...</div>
        ) : threads.length === 0 ? (
          <div className="p-6 text-center text-xs text-slate-500">Aucune conversation trouvée.</div>
        ) : (
          threads.map((t) => {
            const isSelected = t.id === activeThreadId;
            const formattedTime = new Date(t.lastActivityAt).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            });

            return (
              <div
                key={t.id}
                onClick={() => onSelectThread(t.id)}
                className={`p-3 cursor-pointer transition-colors border-l-4 ${
                  isSelected
                    ? "bg-slate-800/90 border-blue-500"
                    : "bg-slate-900/40 border-transparent hover:bg-slate-800/40"
                }`}
              >
                <div className="flex items-start justify-between mb-1">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <span className="font-semibold text-xs text-slate-100 truncate">{t.customerName}</span>
                    {t.customer?.fcrEligible && (
                      <span className="text-[9px] bg-emerald-950 text-emerald-400 border border-emerald-800/80 px-1 py-0.2 rounded font-mono">
                        FCR
                      </span>
                    )}
                  </div>
                  <span className="text-[10px] text-slate-400 font-mono flex-shrink-0">{formattedTime}</span>
                </div>

                <div className="text-[11px] text-slate-400 truncate mb-1 font-mono">{t.customerPhone}</div>

                <div className="flex items-center justify-between text-[11px] text-slate-400 gap-2">
                  <p className="truncate text-slate-300 flex-1">{t.lastMessageSnippet}</p>
                  {t.unreadCount > 0 && (
                    <span className="bg-emerald-500 text-slate-950 font-bold text-[10px] px-1.5 py-0.2 rounded-full flex-shrink-0">
                      {t.unreadCount}
                    </span>
                  )}
                </div>

                {/* Status Indicator */}
                <div className="mt-2 flex items-center justify-between text-[10px] text-slate-500 pt-1 border-t border-slate-800/40">
                  <span className="flex items-center gap-1">
                    {t.status === "ASSIGNED" && <UserCheck className="w-3 h-3 text-blue-400" />}
                    {t.status === "UNASSIGNED" && <ShieldAlert className="w-3 h-3 text-amber-400" />}
                    {t.status === "CLOSED" && <CheckCircle2 className="w-3 h-3 text-slate-500" />}
                    <span>{t.assignedAgentName || "Non attribué"}</span>
                  </span>
                  <span className="uppercase text-[9px] tracking-wider text-slate-400">{t.status}</span>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Footer shortcut bar */}
      <div className="p-2 bg-slate-950 border-t border-slate-800 text-[10px] text-slate-400 flex items-center justify-between font-mono">
        <span>Shortcuts:</span>
        <span>
          <kbd className="px-1 py-0.5 bg-slate-800 rounded border border-slate-700">j</kbd>/
          <kbd className="px-1 py-0.5 bg-slate-800 rounded border border-slate-700">k</kbd> nav |{" "}
          <kbd className="px-1 py-0.5 bg-slate-800 rounded border border-slate-700">r</kbd> reply
        </span>
      </div>
    </aside>
  );
};
