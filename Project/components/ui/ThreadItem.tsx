import { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { MessageSquare } from "lucide-react";

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
        "dashboard-card dashboard-card-interactive w-full p-4 text-left group",
        isActive
          ? "border-brand-primary/20 bg-brand-primary/5 shadow-brand-sm"
          : "hover:bg-brand-surface-container-lowest"
      )}
    >
      <div className="flex items-start gap-3">
        <div className={cn(
          "mt-0.5 rounded-full p-2 transition-colors",
          isActive ? "bg-brand-primary/10" : "bg-brand-surface-container group-hover:bg-brand-primary/10"
        )}>
          <MessageSquare className={cn(
            "w-4 h-4",
            isActive ? "text-brand-primary" : "text-brand-outline group-hover:text-brand-primary"
          )} />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h4 className={cn(
              "font-semibold truncate transition-colors",
              isActive ? "text-brand-on-surface" : "text-brand-on-surface group-hover:text-brand-primary"
            )}>
              {title}
            </h4>
            {hasUnread && (
              <div className="w-2 h-2 rounded-full bg-amber-400 animate-pulse flex-shrink-0" />
            )}
          </div>
          
          {preview && (
            <p className="mt-1 truncate text-xs text-brand-on-surface-variant group-hover:text-brand-on-surface">
              {preview}
            </p>
          )}
        </div>
      </div>
    </button>
  );
}
