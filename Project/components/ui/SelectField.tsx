import { SelectHTMLAttributes, forwardRef, useId } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

interface SelectFieldProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'size'> {
  label?: string;
  error?: string;
  helperText?: string;
  required?: boolean;
  options: SelectOption[];
  placeholder?: string;
  containerClassName?: string;
}

export const SelectField = forwardRef<HTMLSelectElement, SelectFieldProps>(
  ({
    className,
    containerClassName,
    label,
    error,
    helperText,
    required,
    options,
    placeholder,
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

        <div className="relative z-10">
          <select
            ref={ref}
            id={fieldId}
            className={cn(
              "dashboard-field appearance-none px-4 py-3 pr-10 text-sm font-medium",
              error && "border-rose-500/60 focus:border-rose-500/60 focus:ring-rose-500/20",
              className
            )}
            {...props}
          >
            {placeholder && (
              <option value="" disabled>
                {placeholder}
              </option>
            )}
            {options.map((option) => (
              <option
                key={option.value}
                value={option.value}
                disabled={option.disabled}
                className="bg-white text-aura-on-surface"
              >
                {option.label}
              </option>
            ))}
          </select>

          <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-aura-on-surface-variant/60" />
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

SelectField.displayName = "SelectField";
