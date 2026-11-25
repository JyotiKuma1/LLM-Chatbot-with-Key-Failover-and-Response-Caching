import { useState } from "react";
import {
  Database,
  MessageSquare,
  Plus,
  Search,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import type { HealthResponse, SessionSummary } from "../types";

interface SidebarProps {
  sessions: SessionSummary[];
  activeSessionId: string;
  health: HealthResponse | null;
  isOpen: boolean;
  onClose: () => void;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
  onDeleteSession: (sessionId: string) => void;
}

export function Sidebar({
  sessions,
  activeSessionId,
  health,
  isOpen,
  onClose,
  onSelectSession,
  onNewChat,
  onDeleteSession,
}: SidebarProps) {
  const [query, setQuery] = useState("");

  const filtered = query.trim()
    ? sessions.filter((s) =>
        s.title.toLowerCase().includes(query.trim().toLowerCase())
      )
    : sessions;

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/70 md:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-30 w-64 bg-[#18191c] border-r border-white/[0.07] flex flex-col transition-transform duration-200 md:static md:translate-x-0 ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Brand Header */}
        <div className="h-14 px-3.5 flex items-center justify-between border-b border-white/[0.06]">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-teal-500/15 border border-teal-400/30 flex items-center justify-center text-teal-400">
              <Sparkles className="w-4 h-4" />
            </div>
            <span className="font-semibold text-sm tracking-tight text-zinc-100">
              LLM Chatbot
            </span>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close sidebar"
            className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-100 hover:bg-white/[0.06] md:hidden"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* New Chat + Search */}
        <div className="p-3 space-y-2.5 border-b border-white/[0.06]">
          <button
            type="button"
            onClick={() => {
              onNewChat();
              onClose();
            }}
            className="w-full flex items-center justify-between px-3 py-2 rounded-xl bg-white/[0.05] hover:bg-white/[0.09] border border-white/[0.08] text-xs font-medium text-zinc-100 transition cursor-pointer"
          >
            <span className="flex items-center gap-2">
              <Plus className="w-4 h-4 text-teal-400" />
              New Chat
            </span>
            <span className="text-[10px] font-mono text-zinc-500">New</span>
          </button>

          <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-[#121316] border border-white/[0.06] focus-within:border-teal-500/50 transition">
            <Search className="w-3.5 h-3.5 text-zinc-500 shrink-0" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search chats..."
              className="w-full bg-transparent text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none"
            />
          </div>
        </div>

        {/* Recent Chats */}
        <div className="flex-1 overflow-y-auto px-2.5 py-3 space-y-1">
          <div className="px-2 pb-1 flex items-center justify-between text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
            <span>Recent Chats</span>
            <span>{sessions.length}</span>
          </div>

          {filtered.length === 0 ? (
            <p className="px-2 py-4 text-xs text-zinc-500">
              {sessions.length === 0
                ? "No saved chats yet."
                : "No matching chats."}
            </p>
          ) : (
            filtered.map((s) => {
              const isActive = s.session_id === activeSessionId;
              return (
                <div
                  key={s.session_id}
                  className={`group flex items-center gap-2 rounded-lg px-2.5 py-2 text-xs transition ${
                    isActive
                      ? "bg-teal-500/10 text-teal-200 border border-teal-500/25"
                      : "text-zinc-300 hover:bg-white/[0.05] border border-transparent"
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => {
                      onSelectSession(s.session_id);
                      onClose();
                    }}
                    className="flex-1 flex items-center gap-2 text-left min-w-0 cursor-pointer"
                  >
                    <MessageSquare
                      className={`w-3.5 h-3.5 shrink-0 ${
                        isActive ? "text-teal-400" : "text-zinc-500"
                      }`}
                    />
                    <span className="truncate">{s.title}</span>
                  </button>

                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteSession(s.session_id);
                    }}
                    aria-label="Delete chat"
                    title="Delete chat"
                    className="opacity-0 group-hover:opacity-100 p-1 rounded text-zinc-500 hover:text-red-400 transition cursor-pointer"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              );
            })
          )}
        </div>

        {/* Gateway / Storage Status Footer */}
        <div className="p-3 border-t border-white/[0.06] bg-[#141518]">
          <div className="flex items-center justify-between text-[11px] text-zinc-400">
            <span className="flex items-center gap-1.5">
              <Database className="w-3.5 h-3.5 text-teal-400" />
              SQLite Storage
            </span>
            <span className="text-emerald-400 font-mono text-[10px]">
              {health?.status === "ok" ? "Connected" : "Checking"}
            </span>
          </div>
        </div>
      </aside>
    </>
  );
}
