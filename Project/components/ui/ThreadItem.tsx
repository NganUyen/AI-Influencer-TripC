import { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Check, MessageSquare } from "lucide-react";

interface ThreadItemProps {
  id: string;
  title: string;
  preview?: string;
  isActive: boolean;
  hasUnread?: boolean;
  onClick: () => void;
}

export function ThreadItem({
  id,
  title,
  preview,
  isActive,
  hasUnread,
  onClick
}: ThreadItemProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full text-left rounded-xl border p-4 transition-all duration-200",
        "hover:border-emerald-500/50 group",
        isActive
          ? "border-emerald-500/40 bg-gradient-to-r from-emerald-500/15 to-emerald-500/5 shadow-lg shadow-emerald-500/10"
          : "border-white/[0.08] bg-white/[0.02] hover:bg-white/[0.05]"
      )}
    >
      <div className="flex items-start gap-3">
        <div className={cn(
          "mt-0.5 rounded-full p-2 transition-colors",
          isActive ? "bg-emerald-500/20" : "bg-white/[0.05] group-hover:bg-emerald-500/10"
        )}>
          <MessageSquare className={cn(
            "w-4 h-4",
            isActive ? "text-emerald-300" : "text-zinc-500 group-hover:text-emerald-400"
          )} />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h4 className={cn(
              "font-semibold truncate transition-colors",
              isActive ? "text-emerald-200" : "text-white group-hover:text-emerald-300"
            )}>
              {title}
            </h4>
            {hasUnread && (
              <div className="w-2 h-2 rounded-full bg-amber-400 animate-pulse flex-shrink-0" />
            )}
          </div>
          
          {preview && (
            <p className="text-xs text-zinc-500 truncate mt-1 group-hover:text-zinc-400">
              {preview}
            </p>
          )}
        </div>
      </div>
    </button>
  );
}