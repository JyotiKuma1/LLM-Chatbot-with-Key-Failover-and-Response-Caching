import { useEffect, useRef } from "react";
import { Loader2 } from "lucide-react";
import type { UiMessage } from "../types";
import { AssistantMessage } from "./AssistantMessage";
import { ErrorBanner } from "./ErrorBanner";
import { MessageBubble } from "./MessageBubble";

interface ChatWindowProps {
  messages: UiMessage[];
  loading: boolean;
}

export function ChatWindow({ messages, loading }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6">
      <div className="max-w-3xl mx-auto">
        {messages.map((msg) => {
          if (msg.role === "user") {
            return <MessageBubble key={msg.id} content={msg.content} />;
          }
          if (msg.role === "assistant") {
            return (
              <AssistantMessage
                key={msg.id}
                content={msg.content}
                metadata={msg.metadata}
              />
            );
          }
          return <ErrorBanner key={msg.id} message={msg.content} />;
        })}

        {loading && (
          <div className="flex items-center gap-2 text-xs text-zinc-400 px-3.5 py-2.5 rounded-xl bg-[#1c1e22] border border-white/[0.08] w-fit">
            <Loader2 className="w-4 h-4 animate-spin text-teal-400" />
            <span>Generating response...</span>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}
