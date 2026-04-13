import { TextareaHTMLAttributes, forwardRef, useId } from "react";
import { cn } from "@/lib/utils";

interface TextAreaFieldProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  helperText?: string;
  required?: boolean;
  containerClassName?: string;
  minHeight?: string;
}

export const TextAreaField = forwardRef<HTMLTextAreaElement, TextAreaFieldProps>(
  ({
    className,
    containerClassName,
    label,
    error,
    helperText,
    required,
    minHeight = "92px",
    id,
    ...props
  }, ref) => {
    const generatedId = useId();
    const fieldId = id || generatedId;

    return (
      <div className={cn("w-full", containerClassName)}>
        {label && (
          <label
            htmlFor={fieldId}
            className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.18em] text-aura-on-surface-variant"
          >
            {label}
            {required && <span className="text-rose-400 ml-1">*</span>}
          </label>
        )}

        <textarea
          ref={ref}
          id={fieldId}
          style={{ minHeight }}
          className={cn(
            "dashboard-field resize-y px-4 py-3 text-sm font-medium",
            error && "border-rose-500/60 focus:border-rose-500/60 focus:ring-rose-500/20",
            className
          )}
          {...props}
        />

        {error && (
          <p className="mt-2 text-xs text-rose-400 font-medium">
            {error}
          </p>
        )}

        {helperText && !error && (
          <p className="mt-2 text-xs text-aura-on-surface-variant">
            {helperText}
          </p>
        )}
      </div>
    );
  }
);

TextAreaField.displayName = "TextAreaField";
