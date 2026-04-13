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
          "dashboard-card p-6 transition-all duration-200",
          disabled && "opacity-50 cursor-not-allowed",
          className
        )}
      >
      <legend className="px-1 text-sm font-semibold text-aura-on-surface">
        {title}
      </legend>

      {description && (
        <p className="mt-1 px-1 text-xs leading-relaxed text-aura-on-surface-variant">
          {description}
        </p>
      )}

      <div className="mt-6 space-y-5">
        {children}
      </div>
    </fieldset>
  );
}
