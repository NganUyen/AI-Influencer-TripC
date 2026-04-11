import { HTMLAttributes, ReactNode } from "react";
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
    default: "bg-white border border-aura-outline-variant/10 shadow-aura",
    elevated: "bg-white border border-aura-outline-variant/10 shadow-aura hover:shadow-aura-md transition-shadow duration-200",
    outlined: "bg-white border border-aura-outline-variant/20 shadow-none",
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
        "rounded-2xl",
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