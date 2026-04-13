import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

type StatusBadgeTone = "primary" | "secondary" | "surface" | "node";

interface StatusBadgeProps extends HTMLAttributes<HTMLSpanElement> {
  icon?: string;
  tone?: StatusBadgeTone;
  compact?: boolean;
}

const toneClasses: Record<StatusBadgeTone, string> = {
  primary: "status-badge-primary",
  secondary: "status-badge-secondary",
  surface: "status-badge-surface",
  node: "status-badge-node",
};

export function StatusBadge({
  children,
  className,
  icon,
  tone = "primary",
  compact = false,
  ...props
}: StatusBadgeProps) {
  return (
    <span className={cn("status-badge", toneClasses[tone], compact && "px-3 py-1.5 text-[11px]", className)} {...props}>
      {icon ? <span className="material-symbols-outlined text-base">{icon}</span> : null}
      {children}
    </span>
  );
}
