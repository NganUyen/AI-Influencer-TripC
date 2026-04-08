import { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { AlertCircle, CheckCircle, Clock, Zap } from "lucide-react";

type TimelineVariant = "success" | "warning" | "error" | "info";

interface TimelineItemProps {
  id: string;
  title: string;
  description: string;
  variant?: TimelineVariant;
  timestamp?: string;
  icon?: ReactNode;
}

export function TimelineItem({
  id,
  title,
  description,
  variant = "info",
  timestamp,
  icon
}: TimelineItemProps) {
  const variants = {
    success: {
      dotBg: "bg-emerald-500",
      lineBg: "from-emerald-500/50 to-emerald-500/10",
      cardBg: "bg-gradient-to-r from-emerald-500/10 to-emerald-500/5",
      cardBorder: "border-emerald-500/20",
      icon: <CheckCircle className="w-5 h-5 text-emerald-500" />,
    },
    warning: {
      dotBg: "bg-amber-500",
      lineBg: "from-amber-500/50 to-amber-500/10",
      cardBg: "bg-gradient-to-r from-amber-500/10 to-amber-500/5",
      cardBorder: "border-amber-500/20",
      icon: <AlertCircle className="w-5 h-5 text-amber-500" />,
    },
    error: {
      dotBg: "bg-rose-500",
      lineBg: "from-rose-500/50 to-rose-500/10",
      cardBg: "bg-gradient-to-r from-rose-500/10 to-rose-500/5",
      cardBorder: "border-rose-500/20",
      icon: <AlertCircle className="w-5 h-5 text-rose-500" />,
    },
    info: {
      dotBg: "bg-sky-500",
      lineBg: "from-sky-500/50 to-sky-500/10",
      cardBg: "bg-gradient-to-r from-sky-500/10 to-sky-500/5",
      cardBorder: "border-sky-500/20",
      icon: <Zap className="w-5 h-5 text-sky-500" />,
    },
  };

  const style = variants[variant];

  return (
    <div className="flex gap-4">
      {/* Timeline line and dot */}
      <div className="flex flex-col items-center">
        <div className={cn(
          "w-5 h-5 rounded-full border-2 border-aura-surface flex items-center justify-center flex-shrink-0",
          style.dotBg
        )}>
          <div className="w-2 h-2 rounded-full bg-white" />
        </div>
        <div className={cn(
          "w-0.5 my-2 flex-grow bg-gradient-to-b",
          style.lineBg
        )} />
      </div>

      {/* Content card */}
      <div className={cn(
        "flex-1 rounded-lg border p-4 transition-all duration-200",
        "hover:shadow-aura-sm",
        style.cardBg,
        style.cardBorder
      )}>
        <div className="flex items-start gap-3 mb-2">
          {icon || style.icon}
          <div className="flex-1">
            <h4 className="font-semibold text-aura-on-surface text-sm">
              {title}
            </h4>
            {timestamp && (
              <p className="text-xs text-aura-on-surface-variant mt-0.5">
                {timestamp}
              </p>
            )}
          </div>
        </div>

        <p className="text-sm text-aura-on-surface-variant ml-8">
          {description}
        </p>
      </div>
    </div>
  );
}