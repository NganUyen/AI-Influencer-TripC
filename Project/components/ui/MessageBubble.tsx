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
        "dashboard-icon-tile h-10 w-10 flex-shrink-0",
        isAssistant ? "bg-brand-primary/10 text-brand-primary" : "bg-brand-primary text-brand-on-primary"
      )}>
        {isAssistant ? (
          <Bot className="h-5 w-5" />
        ) : (
          <User className="h-5 w-5" />
        )}
      </div>

      <div
        className={cn(
          "max-w-sm rounded-card border px-5 py-4 transition-all duration-300 lg:max-w-xl",
          isAssistant
            ? "bg-brand-surface-container-low text-brand-on-surface border-brand-outline-variant/20"
            : "ml-auto bg-brand-primary text-brand-on-primary border-brand-primary/10"
        )}
      >
        <p className={cn(
          "mb-2 text-[10px] font-bold uppercase tracking-[0.2em]",
          isAssistant ? "text-brand-on-surface-variant/60" : "text-brand-on-primary/70",
        )}>
          {role}
        </p>
        <p className="font-body text-[15px] leading-relaxed whitespace-pre-wrap break-words">
          {content}
        </p>
        {timestamp && (
          <p className={cn(
            "mt-3 text-[10px] font-medium uppercase tracking-wider",
            isAssistant ? "text-brand-on-surface-variant/70" : "text-brand-on-primary/70",
          )}>
            {timestamp}
          </p>
        )}
      </div>
    </div>
  );
}
