import React from 'react'
import { cn } from '../../lib/utils'

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  compact?: boolean
}

export const Card: React.FC<CardProps> = ({
  className,
  compact = false,
  children,
  ...props
}) => {
  return (
    <div
      className={cn(
        'rounded-sm border border-[#829783]/30 dark:border-[#829783]/25 bg-[#FFFEFA] dark:bg-[#1E211E] text-[#292D29] dark:text-[#F5F2EA] shadow-[0_1px_3px_rgba(36,75,59,0.04)] transition-colors',
        compact ? 'p-3' : '',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export const CardHeader: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className,
  children,
  ...props
}) => {
  return (
    <div
      className={cn(
        'flex flex-col space-y-1 p-4 pb-3 border-b border-[#DCE5D9]/60 dark:border-[#829783]/20',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export const CardTitle: React.FC<React.HTMLAttributes<HTMLHeadingElement>> = ({
  className,
  children,
  ...props
}) => {
  return (
    <h3
      className={cn(
        'text-sm font-semibold tracking-tight text-[#18372C] dark:text-[#F5F2EA] flex items-center gap-2',
        className
      )}
      {...props}
    >
      {children}
    </h3>
  )
}

export const CardDescription: React.FC<React.HTMLAttributes<HTMLParagraphElement>> = ({
  className,
  children,
  ...props
}) => {
  return (
    <p
      className={cn('text-xs text-[#73766F] dark:text-[#829783]', className)}
      {...props}
    >
      {children}
    </p>
  )
}

export const CardContent: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className,
  children,
  ...props
}) => {
  return (
    <div className={cn('p-4', className)} {...props}>
      {children}
    </div>
  )
}

export const CardFooter: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className,
  children,
  ...props
}) => {
  return (
    <div
      className={cn(
        'flex items-center p-4 pt-3 border-t border-slate-100 dark:border-slate-800/60 bg-slate-50/50 dark:bg-slate-950/20 text-xs',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}
