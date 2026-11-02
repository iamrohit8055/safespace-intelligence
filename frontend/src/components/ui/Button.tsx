import React from 'react'
import { cn } from '../../lib/utils'

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger'
  size?: 'xs' | 'sm' | 'md' | 'lg'
  isLoading?: boolean
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = 'primary',
      size = 'md',
      isLoading = false,
      disabled,
      children,
      type = 'button',
      ...props
    },
    ref
  ) => {
    const baseStyles =
      'inline-flex items-center justify-center font-medium rounded-sm transition-all select-none focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#244B3B] dark:focus-visible:ring-[#DCE5D9] focus-visible:ring-offset-1 disabled:opacity-50 disabled:pointer-events-none cursor-pointer tracking-tight'

    const sizeStyles = {
      xs: 'h-7 px-2 text-[11px] gap-1',
      sm: 'h-8 px-2.5 text-xs gap-1.5',
      md: 'h-9 px-3.5 text-xs gap-2',
      lg: 'h-10 px-4 text-sm gap-2',
    }

    const variantStyles = {
      primary:
        'bg-[#244B3B] text-[#FFFEFA] hover:bg-[#18372C] active:bg-[#122820] dark:bg-[#DCE5D9] dark:text-[#18372C] dark:hover:bg-[#829783] border border-transparent shadow-xs',
      secondary:
        'bg-[#DCE5D9]/70 text-[#18372C] hover:bg-[#DCE5D9] active:bg-[#DCE5D9]/90 dark:bg-[#1F221F] dark:text-[#DCE5D9] dark:hover:bg-[#292D29] border border-[#829783]/30',
      outline:
        'border border-[#829783]/40 bg-[#FFFEFA] dark:bg-[#1F221F] text-[#292D29] dark:text-[#F5F2EA] hover:bg-[#F5F2EA] dark:hover:bg-[#18372C]/30 active:bg-[#EBF0EA]',
      ghost:
        'bg-transparent text-[#73766F] dark:text-[#829783] hover:bg-[#DCE5D9]/30 dark:hover:bg-[#1F221F] hover:text-[#292D29] dark:hover:text-[#F5F2EA]',
      danger:
        'bg-[#C36B48] text-[#FFFEFA] hover:bg-[#A25335] active:bg-[#8E4327] border border-transparent shadow-xs',
    }

    return (
      <button
        ref={ref}
        type={type}
        disabled={disabled || isLoading}
        className={cn(baseStyles, sizeStyles[size], variantStyles[variant], className)}
        {...props}
      >
        {isLoading && (
          <svg
            className="animate-spin -ml-0.5 mr-1.5 h-3.5 w-3.5 text-current"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            ></circle>
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            ></path>
          </svg>
        )}
        {children}
      </button>
    )
  }
)

Button.displayName = 'Button'
