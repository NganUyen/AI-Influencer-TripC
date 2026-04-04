import { ReactNode, InputHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/utils";

interface FormFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'size'> {
  label?: string;
  error?: string;
  helperText?: string;
  required?: boolean;
  startIcon?: ReactNode;
  endIcon?: ReactNode;
  containerClassName?: string;
}

export const FormField = forwardRef<HTMLInputElement, FormFieldProps>(
  ({
    className,
    containerClassName,
    label,
    error,
    helperText,
    required,
    startIcon,
    endIcon,
    id,
    ...props
  }, ref) => {
    const fieldId = id || `field-${Math.random().toString(36).substr(2, 9)}`;

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

        <div className="relative">
          {startIcon && (
            <div className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500">
              {startIcon}
            </div>
          )}

          <input
            ref={ref}
            id={fieldId}
            className={cn(
              "w-full rounded-xl border bg-white/[0.03] backdrop-blur-xl px-4 py-3 text-sm text-white placeholder:text-zinc-500 outline-none transition-all duration-200",
              "border-white/[0.08] hover:border-white/[0.12] focus:border-emerald-500/60 focus:ring-2 focus:ring-emerald-500/20",
              error && "border-rose-500/60 focus:border-rose-500/60 focus:ring-rose-500/20",
              startIcon && "pl-10",
              endIcon && "pr-10",
              className
            )}
            {...props}
          />

          {endIcon && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500">
              {endIcon}
            </div>
          )}
        </div>

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

FormField.displayName = "FormField";