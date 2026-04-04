import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface FieldSetProps {
  title: string;
  description?: string;
  children: ReactNode;
  disabled?: boolean;
  className?: string;
}

export function FieldSet({
  title,
  description,
  children,
  disabled = false,
  className
}: FieldSetProps) {
  return (
    <fieldset
      disabled={disabled}
      className={cn(
        "rounded-lg border border-white/[0.08] bg-white/[0.02] backdrop-blur-xl p-6 transition-all duration-200",
        disabled && "opacity-50 cursor-not-allowed",
        className
      )}
    >
      <legend className="px-3 font-semibold text-white text-base">
        {title}
      </legend>

      {description && (
        <p className="px-3 mt-1 text-sm text-zinc-400">
          {description}
        </p>
      )}

      <div className="mt-6 space-y-5">
        {children}
      </div>
    </fieldset>
  );
}