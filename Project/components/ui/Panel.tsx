import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

interface PanelProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  variant?: "default" | "elevated" | "outlined";
  padding?: "none" | "sm" | "md" | "lg";
}

export function Panel({
  className,
  children,
  variant = "default",
  padding = "md",
  ...props
}: PanelProps) {
  const variants = {
    default: "dashboard-panel",
    elevated: "dashboard-panel dashboard-card-interactive",
    outlined: "dashboard-panel border-aura-outline-variant/22 shadow-none",
  };

  const paddings = {
    none: "",
    sm: "p-4",
    md: "p-6",
    lg: "p-8",
  };

  return (
    <div
      className={cn(
        variants[variant],
        paddings[padding],
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}
