import { useRef, useState } from "react";
import { ArrowUp, Plus } from "lucide-react";
import type { UiMessage } from "../types";

const MAX_MESSAGE_CHARS = 4000;

interface ChatInputProps {
  onSend: (text: string) => void;
  onNewChat: () => void;
  loading: boolean;
  messages: UiMessage[];
}

export function ChatInput({
  onSend,
  onNewChat,
  loading,
  messages,
}: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || loading) return;
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
    onSend(trimmed);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
  };

  const assistantMessages = messages.filter(
    (m) => m.role === "assistant" && m.metadata
  );
  const totalIn = assistantMessages.reduce(
    (acc, m) => acc + (m.metadata?.input_tokens ?? 0),
    0
  );
  const totalOut = assistantMessages.reduce(
    (acc, m) => acc + (m.metadata?.output_tokens ?? 0),
    0
  );
  const cacheHits = assistantMessages.filter(
    (m) => m.metadata?.resolution_source === "LLM_CACHE"
  ).length;
  const lastMeta =
    assistantMessages.length > 0
      ? assistantMessages[assistantMessages.length - 1].metadata
      : undefined;

  const charCount = value.trim().length;
  const overLimit = charCount > MAX_MESSAGE_CHARS;

  return (
    <div className="rounded-2xl bg-[#1c1e21] border border-white/[0.08] focus-within:border-teal-500/40 shadow-2xl px-4 pt-3.5 pb-2.5 transition">
      <textarea
        ref={textareaRef}
        data-testid="chat-input"
        rows={2}
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder="Ask anything... (Enter to send, Shift+Enter for newline)"
        className="w-full bg-transparent text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none resize-none max-h-40"
      />

      <div className="mt-2.5 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onNewChat}
            title="Start new chat"
            aria-label="Start new chat"
            className="p-1.5 rounded-lg bg-white/[0.05] hover:bg-white/[0.1] border border-white/[0.07] text-zinc-300 hover:text-white transition cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>

          {lastMeta && (
            <span className="text-[11px] text-zinc-400 font-mono hidden sm:inline">
              {lastMeta.model} ·{" "}
              {lastMeta.resolution_source === "LLM_CACHE"
                ? "LLM_CACHE"
                : lastMeta.key_id ?? "live"}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2.5">
          <span
            className={`text-[11px] font-mono ${
              overLimit ? "text-red-400" : "text-zinc-500"
            }`}
          >
            {charCount}/{MAX_MESSAGE_CHARS}
          </span>

          <button
            type="button"
            data-testid="send-button"
            onClick={submit}
            disabled={loading || !value.trim()}
            aria-label="Send message"
            className="p-2 rounded-full bg-teal-400 text-zinc-950 hover:bg-teal-300 disabled:opacity-35 disabled:hover:bg-teal-400 transition cursor-pointer disabled:cursor-not-allowed shadow-sm"
          >
            <ArrowUp className="w-4 h-4 stroke-[2.5]" />
          </button>
        </div>
      </div>

      {assistantMessages.length > 0 && (
        <div className="mt-2.5 pt-2 border-t border-white/[0.06] flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-[11px] text-zinc-400">
          <span className="font-mono">
            Tokens In/Out:{" "}
            <span className="text-teal-300">
              {totalIn} / {totalOut}
            </span>
          </span>
          <div className="flex items-center gap-3 font-mono">
            <span>
              Cache hits:{" "}
              <span className="text-teal-300">{cacheHits}</span>
            </span>
            <span>Turns: {assistantMessages.length}</span>
          </div>
        </div>
      )}
    </div>
  );
}
