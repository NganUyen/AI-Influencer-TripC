import { cn } from "@/lib/utils";
import { Bot, User } from "lucide-react";

interface MessageBubbleProps {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
}

export function MessageBubble({
  id,
  role,
  content,
  timestamp
}: MessageBubbleProps) {
  const isAssistant = role === "assistant";

  return (
    <div
      key={id}
      className={cn(
        "flex gap-3 animate-fadeIn",
        isAssistant ? "justify-start" : "justify-end"
      )}
    >
      {isAssistant && (
        <div className="w-8 h-8 rounded-lg bg-emerald-500/20 flex items-center justify-center flex-shrink-0">
          <Bot className="w-4 h-4 text-emerald-300" />
        </div>
      )}

      <div
        className={cn(
          "max-w-xs lg:max-w-md px-4 py-3 rounded-xl border transition-all duration-200",
          isAssistant
            ? "border-emerald-500/20 bg-gradient-to-br from-emerald-500/10 to-emerald-600/5 text-stone-100"
            : "border-sky-500/20 bg-gradient-to-br from-sky-500/10 to-sky-600/5 text-stone-100 ml-auto"
        )}
      >
        <p className="text-xs font-medium uppercase tracking-widest text-zinc-500 mb-1">
          {role}
        </p>
        <p className="text-sm whitespace-pre-wrap leading-relaxed break-words">
          {content}
        </p>
        {timestamp && (
          <p className="text-xs text-zinc-600 mt-2">
            {timestamp}
          </p>
        )}
      </div>

      {!isAssistant && (
        <div className="w-8 h-8 rounded-lg bg-sky-500/20 flex items-center justify-center flex-shrink-0">
          <User className="w-4 h-4 text-sky-300" />
        </div>
      )}
    </div>
  );
}