import { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { AlertCircle, CheckCircle, Clock } from "lucide-react";

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
      cardBg: "bg-white",
      cardBorder: "border-aura-tertiary/20",
      icon: <CheckCircle className="w-5 h-5 text-aura-tertiary" />,
      titleColor: "text-aura-on-surface",
      textColor: "text-aura-on-surface-variant",
    },
    warning: {
      dotBg: "bg-aura-secondary",
      lineBg: "from-aura-secondary/50 to-aura-secondary/10",
      cardBg: "bg-white",
      cardBorder: "border-aura-secondary/20",
      icon: <AlertCircle className="w-5 h-5 text-aura-secondary" />,
      titleColor: "text-aura-on-surface",
      textColor: "text-aura-on-surface-variant",
    },
    error: {
      dotBg: "bg-aura-secondary",
      lineBg: "from-aura-secondary/50 to-aura-secondary/10",
      cardBg: "bg-white",
      cardBorder: "border-aura-secondary/20",
      icon: <AlertCircle className="w-5 h-5 text-aura-secondary" />,
      titleColor: "text-aura-on-surface",
      textColor: "text-aura-on-surface-variant",
    },
    info: {
      dotBg: "bg-aura-on-surface-variant",
      lineBg: "from-aura-outline-variant/60 to-aura-surface-container-high",
      cardBg: "bg-white",
      cardBorder: "border-aura-outline-variant/20",
      icon: <Clock className="w-5 h-5 text-aura-on-surface-variant" />,
      titleColor: "text-aura-on-surface",
      textColor: "text-aura-on-surface-variant",
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
        "flex-1 rounded-2xl border px-5 py-4 transition-all duration-300 shadow-sm hover:shadow-aura-sm relative overflow-hidden",
        style.cardBg,
        style.cardBorder
      )}>
        <div className="relative z-10 mb-3 flex items-start gap-3">
          {icon || style.icon}
          <div className="flex-1">
            <h4 className={cn("text-[15px] font-extrabold leading-5 font-headline", style.titleColor)}>
              {title}
            </h4>
            {timestamp && (
              <p className={cn("mt-1 text-[11px]", style.textColor)}>
                {timestamp}
              </p>
            )}
          </div>
        </div>

        <p className={cn("relative z-10 ml-8 text-[13px] leading-6", style.textColor)}>
          {description}
        </p>
      </div>
    </div>
  );
}
