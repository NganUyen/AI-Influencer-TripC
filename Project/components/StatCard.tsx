import { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { LucideIcon } from "lucide-react";

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: LucideIcon;
  tone?: "emerald" | "amber" | "sky" | "rose" | "neutral";
  className?: string;
}

export function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  tone = "neutral",
  className
}: StatCardProps) {
  const toneStyles = {
    emerald: {
      gradient: "from-emerald-500 to-emerald-600",
      bg: "bg-emerald-50 dark:bg-emerald-950/20",
      text: "text-emerald-700 dark:text-emerald-300",
      border: "border-emerald-200 dark:border-emerald-800",
    },
    amber: {
      gradient: "from-amber-500 to-amber-600",
      bg: "bg-amber-50 dark:bg-amber-950/20",
      text: "text-amber-700 dark:text-amber-300",
      border: "border-amber-200 dark:border-amber-800",
    },
    sky: {
      gradient: "from-sky-500 to-sky-600",
      bg: "bg-sky-50 dark:bg-sky-950/20",
      text: "text-sky-700 dark:text-sky-300",
      border: "border-sky-200 dark:border-sky-800",
    },
    rose: {
      gradient: "from-rose-500 to-rose-600",
      bg: "bg-rose-50 dark:bg-rose-950/20",
      text: "text-rose-700 dark:text-rose-300",
      border: "border-rose-200 dark:border-rose-800",
    },
    neutral: {
      gradient: "from-gray-500 to-gray-600",
      bg: "bg-gray-50 dark:bg-gray-950/20",
      text: "text-gray-700 dark:text-gray-300",
      border: "border-gray-200 dark:border-gray-800",
    },
  };

  const style = toneStyles[tone];

  return (
    <div className={cn(
      "relative overflow-hidden rounded-xl border p-6 transition-all duration-200 hover:shadow-lg",
      style.bg,
      style.border,
      className
    )}>
      {/* Gradient background accent */}
      <div className={cn(
        "absolute top-0 right-0 w-24 h-24 bg-gradient-to-br opacity-10 rounded-full -translate-y-8 translate-x-8",
        style.gradient
      )} />

      <div className="relative">
        <div className="flex items-center justify-between">
          <div className="flex-1">
            <p className="text-sm font-medium text-gray-600 dark:text-gray-400">
              {title}
            </p>
            <p className={cn("text-2xl font-bold mt-1", style.text)}>
              {value}
            </p>
            {subtitle && (
              <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">
                {subtitle}
              </p>
            )}
          </div>
          {Icon && (
            <div className={cn(
              "p-3 rounded-lg bg-gradient-to-br",
              style.gradient
            )}>
              <Icon className="h-6 w-6 text-white" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}