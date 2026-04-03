import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface DataCardProps {
  children: ReactNode;
  tone?: "emerald" | "amber" | "sky" | "rose" | "neutral";
  className?: string;
  onClick?: () => void;
}

export function DataCard({
  children,
  tone = "neutral",
  className,
  onClick
}: DataCardProps) {
  const toneStyles = {
    emerald: "border-l-emerald-500 bg-emerald-50/50 dark:bg-emerald-950/10 hover:bg-emerald-50 dark:hover:bg-emerald-950/20",
    amber: "border-l-amber-500 bg-amber-50/50 dark:bg-amber-950/10 hover:bg-amber-50 dark:hover:bg-amber-950/20",
    sky: "border-l-sky-500 bg-sky-50/50 dark:bg-sky-950/10 hover:bg-sky-50 dark:hover:bg-sky-950/20",
    rose: "border-l-rose-500 bg-rose-50/50 dark:bg-rose-950/10 hover:bg-rose-50 dark:hover:bg-rose-950/20",
    neutral: "border-l-gray-500 bg-gray-50/50 dark:bg-gray-950/10 hover:bg-gray-50 dark:hover:bg-gray-50/20",
  };

  return (
    <div
      className={cn(
        "border-l-4 p-4 rounded-r-lg transition-colors duration-200 cursor-pointer",
        toneStyles[tone],
        className
      )}
      onClick={onClick}
    >
      {children}
    </div>
  );
}