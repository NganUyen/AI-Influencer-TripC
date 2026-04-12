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
        "flex gap-4 animate-fadeIn",
        isAssistant ? "justify-start" : "justify-end flex-row-reverse"
      )}
    >
      <div className={cn(
        "w-9 h-9 rounded-2xl flex items-center justify-center flex-shrink-0 border border-white/5",
        isAssistant ? "bg-white/[0.03]" : "bg-white text-black"
      )}>
        {isAssistant ? (
          <Bot className="w-5 h-5 text-white/40" />
        ) : (
          <User className="w-5 h-5" />
        )}
      </div>

      <div
        className={cn(
          "max-w-sm lg:max-w-xl px-6 py-4 rounded-[24px] transition-all duration-300",
          isAssistant
            ? "apple-glass text-white/90"
            : "bg-white/[0.05] border border-white/10 text-white ml-auto"
        )}
      >
        <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-white/30 mb-2">
          {role}
        </p>
        <p className="text-[15px] whitespace-pre-wrap leading-relaxed break-words font-body">
          {content}
        </p>
        {timestamp && (
          <p className="text-[10px] text-white/20 mt-3 font-medium uppercase tracking-wider">
            {timestamp}
          </p>
        )}
      </div>
    </div>
  );
}