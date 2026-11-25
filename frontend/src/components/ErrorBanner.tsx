import { AlertCircle } from "lucide-react";

interface ErrorBannerProps {
  message: string | null;
}

export function ErrorBanner({ message }: ErrorBannerProps) {
  if (!message) return null;

  return (
    <div className="mb-4 flex items-start gap-2.5 rounded-xl bg-red-950/80 border border-red-800/80 text-red-200 px-4 py-3 text-xs shadow-sm">
      <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
      <span className="leading-relaxed">{message}</span>
    </div>
  );
}
