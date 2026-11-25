import type { ChatMetadata } from "../types";

interface AssistantMessageProps {
  content: string;
  metadata?: ChatMetadata;
}

export function AssistantMessage({ content, metadata }: AssistantMessageProps) {
  const isCache = metadata?.resolution_source === "LLM_CACHE";

  return (
    <div className="flex flex-col items-start mb-5" data-testid="assistant-message">
      <div className="max-w-[85%] rounded-2xl rounded-tl-sm bg-[#1c1e22] border border-white/[0.08] text-zinc-100 px-4 py-3 text-sm shadow-sm leading-relaxed whitespace-pre-wrap">
        <p>{content}</p>
      </div>

      {metadata && (
        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-zinc-400 px-1">
          <span>
            <span>Source: </span>
            <span
              data-testid="meta-source"
              className={`font-mono px-1.5 py-0.5 rounded text-[10px] ${isCache
                  ? "bg-teal-500/15 text-teal-300 border border-teal-500/30"
                  : "bg-zinc-800 text-zinc-200 border border-white/[0.08]"
                }`}
            >
              {metadata.resolution_source}
            </span>
          </span>

          <span>
            <span>Model: </span>
            <span data-testid="meta-model" className="font-mono text-zinc-300">
              {metadata.model}
            </span>
          </span>

          <span>
            <span>Latency: </span>
            <span data-testid="meta-latency" className="font-mono text-zinc-300">
              {metadata.latency_ms} ms
            </span>
          </span>

          <span>
            <span>In: </span>
            <span data-testid="meta-input-tokens" className="font-mono text-zinc-300">
              {metadata.input_tokens}
            </span>
          </span>

          <span>
            <span>Out: </span>
            <span data-testid="meta-output-tokens" className="font-mono text-zinc-300">
              {metadata.output_tokens}
            </span>
          </span>
        </div>
      )}
    </div>
  );
}
