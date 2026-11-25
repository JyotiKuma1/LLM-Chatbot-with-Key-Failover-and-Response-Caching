interface MessageBubbleProps {
  content: string;
}

export function MessageBubble({ content }: MessageBubbleProps) {
  return (
    <div className="flex justify-end mb-4">
      <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-teal-600/20 border border-teal-500/30 text-zinc-100 px-4 py-3 text-sm shadow-sm leading-relaxed whitespace-pre-wrap">
        {content}
      </div>
    </div>
  );
}
