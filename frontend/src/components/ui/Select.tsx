import React from 'react'
import { cn } from '../../lib/utils'

export interface SelectOption {
  value: string | number
  label: string
}

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  error?: string
  options?: SelectOption[]
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, label, error, options, children, id, ...props }, ref) => {
    const selectId = id || props.name || Math.random().toString(36).substring(2, 9)

    return (
      <div className="w-full flex flex-col gap-1">
        {label && (
          <label
            htmlFor={selectId}
            className="text-[10px] font-mono uppercase tracking-wider text-[#73766F] dark:text-[#829783] select-none"
          >
            {label}
          </label>
        )}
        <select
          ref={ref}
          id={selectId}
          className={cn(
            'flex h-9 w-full rounded-sm border border-[#829783]/40 dark:border-[#829783]/30 bg-[#FFFEFA] dark:bg-[#1E211E] px-3 py-1.5 text-xs text-[#292D29] dark:text-[#F5F2EA] focus:outline-none focus:ring-1 focus:ring-[#244B3B] dark:focus:ring-[#DCE5D9] focus:border-[#244B3B] dark:focus:border-[#DCE5D9] disabled:cursor-not-allowed disabled:opacity-50 transition-colors shadow-2xs cursor-pointer',
            error && 'border-[#C36B48] focus:ring-[#C36B48] focus:border-[#C36B48]',
            className
          )}
          {...props}
        >
          {options
            ? options.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))
            : children}
        </select>
        {error && <span className="text-[11px] text-[#C36B48] font-medium">{error}</span>}
      </div>
    )
  }
)

Select.displayName = 'Select'
