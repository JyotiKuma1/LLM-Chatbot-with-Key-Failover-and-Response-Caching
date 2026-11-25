import { useState } from "react";
import {
  ChevronDown,
  Clock,
  Database,
  Menu,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { ChatInput } from "./components/ChatInput";
import { ChatWindow } from "./components/ChatWindow";
import { Sidebar } from "./components/Sidebar";
import { SystemPromptInput } from "./components/SystemPromptInput";
import { useChat } from "./hooks/useChat";

const SUGGESTIONS = [
  "What is the capital of France?",
  "Explain how LLM response caching reduces latency",
  "How does multi-key failover handle 429 rate limits?",
  "Write a Python retry helper with exponential backoff",
];

export default function App() {
  const {
    sessionId,
    sessions,
    health,
    models,
    selectedModel,
    setSelectedModel,
    messages,
    loading,
    systemPrompt,
    setSystemPrompt,
    send,
    selectSession,
    startNewChat,
    removeSession,
  } = useChat();

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const isEmpty = messages.length === 0 && !loading;

  const lastAssistant = [...messages]
    .reverse()
    .find((m) => m.role === "assistant" && m.metadata);

  return (
    <div className="flex h-screen bg-[#121315] text-zinc-100 font-sans overflow-hidden">
      <Sidebar
        sessions={sessions}
        activeSessionId={sessionId}
        health={health}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onSelectSession={(id) => void selectSession(id)}
        onNewChat={startNewChat}
        onDeleteSession={(id) => void removeSession(id)}
      />

      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Bar */}
        <header className="h-14 px-4 md:px-6 flex items-center justify-between border-b border-white/[0.06] bg-[#141518]/80 backdrop-blur-sm">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setSidebarOpen(true)}
              aria-label="Open sidebar"
              className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/[0.06] md:hidden"
            >
              <Menu className="w-5 h-5" />
            </button>

            <div className="relative flex items-center px-3 py-1 rounded-full bg-white/[0.05] border border-white/[0.08] hover:border-teal-500/40 text-xs text-zinc-200 transition">
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                aria-label="Select Gemini model"
                className="appearance-none bg-transparent pr-5 font-mono text-[11px] text-zinc-200 focus:outline-none cursor-pointer"
              >
                {models.map((m) => (
                  <option key={m} value={m} className="bg-[#18191c] text-zinc-100">
                    {m}
                  </option>
                ))}
              </select>
              <ChevronDown className="w-3.5 h-3.5 text-zinc-400 absolute right-2 pointer-events-none" />
            </div>

            <span className="hidden sm:flex items-center gap-1 text-[11px] text-zinc-400">
              <Clock className="w-3 h-3" />
              {health?.status === "ok" ? "Online" : "Connecting"}
            </span>
          </div>

          <span className="text-[11px] font-mono text-zinc-500">
            Session: {sessionId.slice(0, 14)}
          </span>
        </header>

        {/* Main Workspace */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {isEmpty ? (
            <div className="flex-1 overflow-y-auto px-4 py-8 flex flex-col items-center justify-center">
              <div className="w-full max-w-2xl mx-auto">
                {/* Centered Hero */}
                <div className="text-center mb-6">
                  <div className="inline-flex p-3 rounded-2xl bg-[#1c1e22] border border-teal-500/25 text-teal-400 shadow-lg shadow-teal-500/5 mb-4">
                    <Sparkles className="w-6 h-6" />
                  </div>
                  <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-zinc-100 mb-2">
                    What do you want to know?
                  </h1>
                  <p className="text-xs sm:text-sm text-zinc-400 max-w-md mx-auto">
                    Multi-turn AI chat with automatic key failover, response caching, and SQLite session persistence.
                  </p>
                </div>

                {/* Centered Composer */}
                <SystemPromptInput
                  value={systemPrompt}
                  onChange={setSystemPrompt}
                />
                <ChatInput
                  onSend={send}
                  onNewChat={startNewChat}
                  loading={loading}
                  messages={messages}
                />

                {/* Adequate Feature Cards */}
                <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="rounded-xl bg-teal-950/25 border border-teal-500/20 p-3.5 flex items-start gap-3">
                    <div className="p-2 rounded-lg bg-teal-500/15 text-teal-400 shrink-0">
                      <ShieldCheck className="w-4 h-4" />
                    </div>
                    <div>
                      <h2 className="text-xs font-semibold text-zinc-100 mb-0.5">
                        Key Failover & Caching
                      </h2>
                      <p className="text-[11px] text-zinc-400 leading-relaxed">
                        Automatic key pool fallback on provider errors with fast local `LLM_CACHE` hits.
                      </p>
                    </div>
                  </div>

                  <div className="rounded-xl bg-[#191b1e] border border-white/[0.07] p-3.5 flex items-start gap-3">
                    <div className="p-2 rounded-lg bg-white/[0.06] text-zinc-300 shrink-0">
                      <Database className="w-4 h-4" />
                    </div>
                    <div>
                      <h2 className="text-xs font-semibold text-zinc-100 mb-0.5">
                        SQLite Multi-Turn History
                      </h2>
                      <p className="text-[11px] text-zinc-400 leading-relaxed">
                        Conversations persist atomically and stay accessible in the sidebar after reload.
                      </p>
                    </div>
                  </div>
                </div>

                {/* Suggested Prompts */}
                <div className="mt-6 text-center">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500 mb-2.5">
                    Suggested Prompts
                  </p>
                  <div className="flex flex-wrap justify-center gap-2">
                    {SUGGESTIONS.map((item) => (
                      <button
                        key={item}
                        type="button"
                        onClick={() => void send(item)}
                        className="px-3 py-1.5 rounded-full bg-[#1a1c1f] hover:bg-white/[0.08] border border-white/[0.07] text-[11px] text-zinc-300 hover:text-white transition cursor-pointer"
                      >
                        {item}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <>
              <ChatWindow messages={messages} loading={loading} />
              <div className="px-4 pb-4 pt-2 bg-[#121315]">
                <div className="max-w-3xl mx-auto">
                  <SystemPromptInput
                    value={systemPrompt}
                    onChange={setSystemPrompt}
                  />
                  <ChatInput
                    onSend={send}
                    onNewChat={startNewChat}
                    loading={loading}
                    messages={messages}
                  />
                </div>
              </div>
            </>
          )}
        </main>

        {/* Subtle Status Footer */}
        <footer className="h-8 px-4 md:px-6 border-t border-white/[0.05] bg-[#121315] flex items-center justify-between text-[10px] font-mono text-zinc-500">
          <span>
            {lastAssistant?.metadata
              ? `${lastAssistant.metadata.resolution_source} // Latency: ${lastAssistant.metadata.latency_ms}ms`
              : "Gateway Ready // SQLite + LiteLLM"}
          </span>
          <span>
            {health
              ? `Pool: ${health.keys_configured} keys · Cache: ${health.cache_enabled ? "On" : "Off"}`
              : "LiteLLM Gateway"}
          </span>
        </footer>
      </div>
    </div>
  );
}
