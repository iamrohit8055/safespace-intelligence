import React from 'react'
import { cn } from '../../lib/utils'

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string
  error?: string
  helperText?: string
}

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, label, error, helperText, id, rows = 3, ...props }, ref) => {
    const textareaId = id || props.name || Math.random().toString(36).substring(2, 9)

    return (
      <div className="w-full flex flex-col gap-1">
        {label && (
          <label
            htmlFor={textareaId}
            className="text-[10px] font-mono uppercase tracking-wider text-[#73766F] dark:text-[#829783] select-none"
          >
            {label}
          </label>
        )}
        <textarea
          ref={ref}
          id={textareaId}
          rows={rows}
          className={cn(
            'flex w-full rounded-sm border border-[#829783]/40 dark:border-[#829783]/30 bg-[#FFFEFA] dark:bg-[#1E211E] px-3 py-2 text-xs text-[#292D29] dark:text-[#F5F2EA] placeholder:text-[#73766F]/60 focus:outline-none focus:ring-1 focus:ring-[#244B3B] dark:focus:ring-[#DCE5D9] focus:border-[#244B3B] dark:focus:border-[#DCE5D9] disabled:cursor-not-allowed disabled:opacity-50 transition-colors shadow-2xs',
            error && 'border-[#C36B48] focus:ring-[#C36B48] focus:border-[#C36B48]',
            className
          )}
          {...props}
        />
        {error && <span className="text-[11px] text-[#C36B48] font-medium">{error}</span>}
        {!error && helperText && (
          <span className="text-[11px] text-[#73766F] dark:text-[#829783]">{helperText}</span>
        )}
      </div>
    )
  }
)

Textarea.displayName = 'Textarea'
