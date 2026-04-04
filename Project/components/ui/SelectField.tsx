import { SelectHTMLAttributes, forwardRef, ReactNode } from "react";
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
    const fieldId = id || `select-${Math.random().toString(36).substr(2, 9)}`;

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
          <select
            ref={ref}
            id={fieldId}
            className={cn(
              "w-full rounded-xl border bg-white/[0.03] backdrop-blur-xl px-4 py-3 pr-10 text-sm text-white placeholder:text-zinc-500 outline-none transition-all duration-200 appearance-none",
              "border-white/[0.08] hover:border-white/[0.12] focus:border-emerald-500/60 focus:ring-2 focus:ring-emerald-500/20",
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
                className="bg-gray-800 text-white"
              >
                {option.label}
              </option>
            ))}
          </select>

          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500 pointer-events-none" />
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

SelectField.displayName = "SelectField";