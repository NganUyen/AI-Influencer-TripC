import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";

type BaseButtonVariant = "primary" | "secondary" | "ghost" | "contrast" | "surface";
type BaseButtonSize = "sm" | "md" | "lg" | "icon";

interface BaseButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  variant?: BaseButtonVariant;
  size?: BaseButtonSize;
  fullWidth?: boolean;
}

const variantClasses: Record<BaseButtonVariant, string> = {
  primary: "btn-primary",
  secondary: "btn-secondary",
  ghost: "btn-ghost",
  contrast: "btn-contrast",
  surface: "btn-surface",
};

const sizeClasses: Record<BaseButtonSize, string> = {
  sm: "btn-sm",
  md: "",
  lg: "btn-lg",
  icon: "btn-icon",
};

export function BaseButton({
  children,
  className,
  variant = "primary",
  size = "md",
  fullWidth = false,
  type = "button",
  ...props
}: BaseButtonProps) {
  return (
    <button
      type={type}
      className={cn(variantClasses[variant], sizeClasses[size], fullWidth && "btn-wide", className)}
      {...props}
    >
      {children}
    </button>
  );
}
