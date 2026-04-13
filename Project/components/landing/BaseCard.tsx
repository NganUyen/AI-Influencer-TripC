import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";

type BaseCardVariant = "default" | "persona" | "feature" | "testimonial" | "accent" | "muted";
type BaseCardPadding = "sm" | "md" | "lg" | "xl";

interface BaseCardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  variant?: BaseCardVariant;
  padding?: BaseCardPadding;
  interactive?: boolean;
}

const variantClasses: Record<BaseCardVariant, string> = {
  default: "landing-card bg-surface-container-lowest text-on-surface",
  persona: "landing-card bg-surface-container-low text-on-surface",
  feature: "landing-card bg-surface-container-lowest text-on-surface",
  testimonial: "landing-card bg-surface-container-lowest text-on-surface",
  accent: "landing-card landing-card-accent bg-gradient-to-br from-primary to-primary-container text-on-primary",
  muted: "landing-card bg-surface-container-low text-on-surface",
};

const paddingClasses: Record<BaseCardPadding, string> = {
  sm: "p-4",
  md: "p-6",
  lg: "p-6 md:p-8",
  xl: "p-6 md:p-10",
};

export function BaseCard({
  children,
  className,
  variant = "default",
  padding = "md",
  interactive = false,
  ...props
}: BaseCardProps) {
  return (
    <div
      className={cn(
        variantClasses[variant],
        paddingClasses[padding],
        interactive && "landing-card-interactive",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}
