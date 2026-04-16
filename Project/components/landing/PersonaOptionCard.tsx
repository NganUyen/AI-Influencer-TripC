import { BaseCard } from "@/components/landing/BaseCard";
import { cn } from "@/lib/utils";

interface PersonaOptionCardProps {
  img: string;
  lang: string;
  category: string;
  active?: boolean;
  onClick?: () => void;
}

export function PersonaOptionCard({
  img,
  lang,
  category,
  active = false,
  onClick,
}: PersonaOptionCardProps) {
  return (
    <BaseCard
      variant="persona"
      padding="sm"
      interactive
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={
        onClick
          ? (event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onClick();
              }
            }
          : undefined
      }
      className={cn(
        "flex min-h-[164px] flex-col items-center justify-center gap-3 text-center cursor-pointer",
        active ? "border-primary ring-2 ring-primary/15" : "border-outline-variant/10 hover:bg-surface-container-high",
      )}
    >
      <div className="h-16 w-16 overflow-hidden rounded-full bg-surface-container-high">
        <img className="h-full w-full object-cover" src={img} alt={lang} />
      </div>
      <div className="space-y-1">
        <span className="block text-sm font-bold text-on-surface">{lang}</span>
        <span className="text-xs text-on-surface-variant/80">{category}</span>
      </div>
    </BaseCard>
  );
}
