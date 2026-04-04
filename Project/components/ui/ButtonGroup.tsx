import { ReactNode, ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

interface ButtonGroupItem {
  label: string;
  onClick: () => void;
  variant?: "primary" | "secondary" | "danger";
  disabled?: boolean;
  loading?: boolean;
  icon?: ReactNode;
}

interface ButtonGroupProps {
  buttons: ButtonGroupItem[];
  size?: "sm" | "md" | "lg";
  orientation?: "horizontal" | "vertical";
  className?: string;
}

export function ButtonGroup({
  buttons,
  size = "md",
  orientation = "horizontal",
  className
}: ButtonGroupProps) {
  const sizeClasses = {
    sm: "px-3 py-1.5 text-xs",
    md: "px-4 py-2 text-sm",
    lg: "px-6 py-3 text-base",
  };

  const variantClasses = {
    primary: "bg-emerald-500 text-white hover:bg-emerald-400 shadow-lg shadow-emerald-500/20 hover:shadow-emerald-500/30",
    secondary: "bg-white/[0.05] text-zinc-300 border border-white/[0.08] hover:bg-white/[0.08] hover:border-white/[0.12]",
    danger: "bg-rose-500 text-white hover:bg-rose-400 shadow-lg shadow-rose-500/20 hover:shadow-rose-500/30",
  };

  return (
    <div className={cn(
      "flex gap-2",
      orientation === "vertical" && "flex-col",
      className
    )}>
      {buttons.map((button, index) => (
        <button
          key={index}
          onClick={button.onClick}
          disabled={button.disabled || button.loading}
          className={cn(
            "inline-flex items-center justify-center rounded-lg font-medium transition-all duration-200 ease-out",
            "focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-emerald-500/20",
            "disabled:opacity-50 disabled:cursor-not-allowed active:scale-[0.98]",
            sizeClasses[size],
            variantClasses[button.variant || "primary"]
          )}
        >
          {button.loading && (
            <svg
              className="animate-spin -ml-1 mr-2 h-4 w-4"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
          )}

          {!button.loading && button.icon && (
            <span className="mr-2">{button.icon}</span>
          )}

          {button.label}
        </button>
      ))}
    </div>
  );
}