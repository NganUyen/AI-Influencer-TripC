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
    <div className={cn("flex items-center justify-between p-6 pb-5", className)}>
      <div className="flex-1">
        <h3 className="text-lg font-extrabold text-aura-on-surface font-headline">
          {title}
        </h3>
        {subtitle && (
          <p className="mt-1.5 max-w-2xl text-xs text-aura-on-surface-variant/80 leading-relaxed">
            {subtitle}
          </p>
        )}
      </div>
      {actions && (
        <div className="flex items-center space-x-2 ml-4">
          {actions}
        </div>
      )}
    </div>
  );
}
