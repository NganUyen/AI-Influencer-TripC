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
    default: "bg-white dark:bg-gray-800 shadow-sm border border-gray-200 dark:border-gray-700",
    elevated: "bg-white dark:bg-gray-800 shadow-lg border border-gray-200 dark:border-gray-700 hover:shadow-xl transition-shadow duration-200",
    outlined: "bg-white dark:bg-gray-800 border-2 border-gray-300 dark:border-gray-600 shadow-none",
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
        "rounded-xl",
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