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
      dotBg: "bg-aura-tertiary",
      lineBg: "from-aura-tertiary/50 to-aura-tertiary/10",
      cardBg: "bg-gradient-to-r from-aura-tertiary/10 to-aura-tertiary/5",
      cardBorder: "border-aura-tertiary/20",
      icon: <CheckCircle className="w-5 h-5 text-aura-tertiary" />,
    },
    warning: {
      dotBg: "bg-aura-secondary",
      lineBg: "from-aura-secondary/50 to-aura-secondary/10",
      cardBg: "bg-gradient-to-r from-aura-secondary/10 to-aura-secondary/5",
      cardBorder: "border-aura-secondary/20",
      icon: <AlertCircle className="w-5 h-5 text-aura-secondary" />,
    },
    error: {
      dotBg: "bg-aura-error",
      lineBg: "from-aura-error/50 to-aura-error/10",
      cardBg: "bg-gradient-to-r from-aura-error/10 to-aura-error/5",
      cardBorder: "border-aura-error/20",
      icon: <AlertCircle className="w-5 h-5 text-aura-error" />,
    },
    info: {
      dotBg: "bg-aura-primary",
      lineBg: "from-aura-primary/50 to-aura-primary/10",
      cardBg: "bg-gradient-to-r from-aura-primary/10 to-aura-primary/5",
      cardBorder: "border-aura-primary/20",
      icon: <Zap className="w-5 h-5 text-aura-primary" />,
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
        "flex-1 rounded-2xl border p-5 transition-all duration-300 shadow-sm hover:shadow-aura-md hover:-translate-y-0.5 relative overflow-hidden",
        style.cardBg,
        style.cardBorder
      )}>
        <div className="flex items-start gap-3 mb-2 relative z-10">
          {icon || style.icon}
          <div className="flex-1">
            <h4 className="font-bold text-aura-on-surface text-sm font-headline">
              {title}
            </h4>
            {timestamp && (
              <p className="text-xs text-aura-on-surface-variant mt-0.5">
                {timestamp}
              </p>
            )}
          </div>
        </div>

        <p className="text-sm text-aura-on-surface-variant ml-8 relative z-10">
          {description}
        </p>
      </div>
    </div>
  );
}