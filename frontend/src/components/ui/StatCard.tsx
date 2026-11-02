import React from 'react'
import { Card } from './Card'
import { cn } from '../../lib/utils'

export interface StatCardProps {
  title: string
  value: string | number
  description?: string
  icon?: React.ReactNode
  trend?: {
    value: string | number
    isPositive?: boolean
    label?: string
  }
  badge?: React.ReactNode
  className?: string
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  description,
  icon,
  trend,
  badge,
  className,
}) => {
  return (
    <Card className={cn('p-3.5 flex flex-col justify-between', className)}>
      <div className="flex items-start justify-between gap-2">
        <span className="text-[10px] font-mono uppercase tracking-wider text-[#73766F] dark:text-[#829783]">
          {title}
        </span>
        {icon && (
          <span className="text-[#829783] dark:text-[#829783] shrink-0">
            {icon}
          </span>
        )}
      </div>

      <div className="mt-2 flex items-baseline justify-between gap-2">
        <div className="text-2xl font-semibold tracking-tight text-[#18372C] dark:text-[#F5F2EA] font-mono-numbers">
          {value}
        </div>
        {badge && <div>{badge}</div>}
      </div>

      {(description || trend) && (
        <div className="mt-2 pt-2 border-t border-[#DCE5D9]/60 dark:border-[#829783]/20 flex items-center justify-between text-[11px] text-[#73766F] dark:text-[#829783]">
          {description && <span className="truncate">{description}</span>}
          {trend && (
            <span
              className={cn(
                'font-mono font-medium ml-auto inline-flex items-center gap-0.5 shrink-0',
                trend.isPositive ? 'text-[#244B3B] dark:text-[#DCE5D9]' : 'text-[#C36B48]'
              )}
            >
              {trend.isPositive ? '↑' : '↓'} {trend.value} {trend.label}
            </span>
          )}
        </div>
      )}
    </Card>
  )
}
