import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface PanelHeaderProps {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  className?: string;
}

export function PanelHeader({ title, subtitle, actions, className }: PanelHeaderProps) {
  return (
    <div className={cn("flex items-start justify-between gap-4 p-6 pb-5", className)}>
      <div className="flex-1">
        <h3 className="font-headline text-lg font-extrabold text-aura-on-surface">
          {title}
        </h3>
        {subtitle && (
          <p className="mt-1.5 max-w-2xl text-xs leading-relaxed text-aura-on-surface-variant/80">
            {subtitle}
          </p>
        )}
      </div>
      {actions && (
        <div className="ml-4 flex items-center gap-2">
          {actions}
        </div>
      )}
    </div>
  );
}
