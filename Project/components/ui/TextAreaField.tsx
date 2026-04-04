import { TextareaHTMLAttributes, forwardRef } from "react";
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
    const fieldId = id || `textarea-${Math.random().toString(36).substr(2, 9)}`;

    return (
      <div className={cn("w-full", containerClassName)}>
        {label && (
          <label
            htmlFor={fieldId}
            className="block text-xs font-semibold uppercase tracking-widest text-zinc-400 mb-2"
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
            "w-full rounded-xl border bg-white/[0.03] backdrop-blur-xl px-4 py-3 text-sm text-white placeholder:text-zinc-500 outline-none transition-all duration-200 resize-y",
            "border-white/[0.08] hover:border-white/[0.12] focus:border-emerald-500/60 focus:ring-2 focus:ring-emerald-500/20",
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
          <p className="mt-2 text-xs text-zinc-500">
            {helperText}
          </p>
        )}
      </div>
    );
  }
);

TextAreaField.displayName = "TextAreaField";