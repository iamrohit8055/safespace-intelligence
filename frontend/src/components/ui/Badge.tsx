import React from 'react'
import { cn, getPriorityColor, getStatusColor } from '../../lib/utils'

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'status' | 'priority' | 'outline' | 'neutral'
  status?: string
  priority?: string
}

export const Badge: React.FC<BadgeProps> = ({
  className,
  variant = 'default',
  status,
  priority,
  children,
  ...props
}) => {
  if (variant === 'status' && status) {
    const sColors = getStatusColor(status)
    return (
      <span
        className={cn(
          'inline-flex items-center gap-1 px-1.5 py-0.5 rounded-xs text-[11px] font-mono font-medium uppercase tracking-tight border',
          sColors.bg,
          sColors.text,
          sColors.border,
          className
        )}
        {...props}
      >
        {children || status.replace(/_/g, ' ')}
      </span>
    )
  }

  if (variant === 'priority' && priority) {
    const pColors = getPriorityColor(priority)
    return (
      <span
        className={cn(
          'inline-flex items-center gap-1.5 px-1.5 py-0.5 rounded-xs text-[11px] font-mono font-medium uppercase tracking-tight border',
          pColors.bg,
          pColors.text,
          pColors.border,
          className
        )}
        {...props}
      >
        <span className={cn('h-1.5 w-1.5 rounded-full shrink-0', pColors.dot)} />
        {children || priority.replace(/_/g, ' ')}
      </span>
    )
  }

  if (variant === 'outline') {
    return (
      <span
        className={cn(
          'inline-flex items-center px-1.5 py-0.5 rounded-xs text-[11px] font-mono font-medium border border-[#829783]/40 text-[#292D29] dark:text-[#F5F2EA] bg-transparent',
          className
        )}
        {...props}
      >
        {children}
      </span>
    )
  }

  return (
    <span
      className={cn(
        'inline-flex items-center px-1.5 py-0.5 rounded-xs text-[11px] font-mono font-medium bg-[#DCE5D9]/40 dark:bg-[#1F221F] text-[#18372C] dark:text-[#DCE5D9] border border-[#829783]/30',
        className
      )}
      {...props}
    >
      {children}
    </span>
  )
}
