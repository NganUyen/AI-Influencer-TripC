import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface PersonaCardProps {
  id: string;
  name: string;
  avatarUrl?: string;
  status: string;
  videoCount?: number;
  tone?: "emerald" | "amber" | "sky" | "rose";
  onClick?: () => void;
}

export function PersonaCard({
  id,
  name,
  avatarUrl,
  status,
  videoCount = 0,
  tone = "emerald",
  onClick
}: PersonaCardProps) {
  const toneStyles = {
    emerald: {
      gradient: "from-emerald-500/20 to-emerald-600/10",
      border: "border-emerald-500/20",
      accent: "bg-emerald-500/10 text-emerald-300",
    },
    amber: {
      gradient: "from-amber-500/20 to-amber-600/10",
      border: "border-amber-500/20",
      accent: "bg-amber-500/10 text-amber-300",
    },
    sky: {
      gradient: "from-sky-500/20 to-sky-600/10",
      border: "border-sky-500/20",
      accent: "bg-sky-500/10 text-sky-300",
    },
    rose: {
      gradient: "from-rose-500/20 to-rose-600/10",
      border: "border-rose-500/20",
      accent: "bg-rose-500/10 text-rose-300",
    },
  };

  const style = toneStyles[tone];

  return (
    <div
      onClick={onClick}
      className={cn(
        "relative overflow-hidden rounded-xl border p-4 cursor-pointer transition-all duration-300",
        "bg-gradient-to-br",
        style.gradient,
        style.border,
        "hover:shadow-lg hover:shadow-black/20 hover:scale-105 group"
      )}
    >
      {/* Background accent glow */}
      <div className={cn(
        "absolute top-0 right-0 w-32 h-32 rounded-full opacity-0 group-hover:opacity-20 transition-opacity duration-300",
        `bg-gradient-to-br ${style.gradient}`
      )} />

      <div className="relative">
        <div className="flex gap-4">
          {/* Avatar */}
          <div className="w-16 h-16 rounded-lg bg-zinc-800 overflow-hidden flex-shrink-0">
            {avatarUrl ? (
              <img
                src={avatarUrl}
                alt={name}
                className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-300"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-zinc-700 to-zinc-800">
                <span className="text-xs font-semibold text-zinc-400">
                  {name.charAt(0).toUpperCase()}
                </span>
              </div>
            )}
          </div>

          {/* Info */}
          <div className="flex-1 min-w-0">
            <h4 className="font-semibold text-white truncate group-hover:text-emerald-300 transition-colors">
              {name}
            </h4>
            <p className={cn("text-xs font-medium mt-1", style.accent, "rounded px-2 py-0.5 w-fit")}>
              {status.replace(/_/g, " ").toUpperCase()}
            </p>
            {videoCount > 0 && (
              <p className="text-xs text-zinc-400 mt-2">
                {videoCount} video{videoCount !== 1 ? "s" : ""} created
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}