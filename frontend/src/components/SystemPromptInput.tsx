interface SystemPromptInputProps {
  value: string;
  onChange: (value: string) => void;
}

export function SystemPromptInput({ value, onChange }: SystemPromptInputProps) {
  return (
    <div className="mb-2.5 flex items-center gap-2 rounded-xl bg-[#1a1c1f] border border-white/[0.07] px-3 py-1.5 focus-within:border-teal-500/50 transition">
      <span className="text-[11px] font-medium text-zinc-400 shrink-0">
        System
      </span>
      <input
        type="text"
        data-testid="system-prompt-input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Optional system prompt (e.g. You are a helpful assistant.)"
        className="w-full bg-transparent text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none"
      />
    </div>
  );
}
