import { ReactNode, InputHTMLAttributes, forwardRef, useId } from "react";
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

        <div className="relative">
          {startIcon && (
            <div className="absolute left-3 top-1/2 -translate-y-1/2 text-aura-on-surface-variant/60">
              {startIcon}
            </div>
          )}

          <input
            ref={ref}
            id={fieldId}
            className={cn(
              "dashboard-field px-4 py-3 text-sm font-medium",
              error && "border-rose-500/60 focus:border-rose-500/60 focus:ring-rose-500/20",
              startIcon && "pl-10",
              endIcon && "pr-10",
              className
            )}
            {...props}
          />

          {endIcon && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2 text-aura-on-surface-variant/60">
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
          <p className="mt-2 text-xs text-aura-on-surface-variant">
            {helperText}
          </p>
        )}
      </div>
    );
  }
);

FormField.displayName = "FormField";
