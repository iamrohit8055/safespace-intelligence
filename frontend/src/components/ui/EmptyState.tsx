import React from 'react'
import { AlertCircle } from 'lucide-react'
import { Button } from './Button'
import { cn } from '../../lib/utils'

export interface EmptyStateProps {
  icon?: React.ReactNode
  title: string
  description?: string
  actionLabel?: string
  onAction?: () => void
  className?: string
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  actionLabel,
  onAction,
  className,
}) => {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center py-10 px-4 text-center rounded-sm border border-dashed border-[#829783]/40 dark:border-[#829783]/25 bg-[#FAF8F4] dark:bg-[#1E211E]/40',
        className
      )}
    >
      <div className="p-2.5 rounded-sm bg-[#DCE5D9]/40 dark:bg-[#18372C]/40 text-[#18372C] dark:text-[#DCE5D9] mb-2.5">
        {icon || <AlertCircle className="h-5 w-5" />}
      </div>
      <h3 className="text-sm font-medium text-[#18372C] dark:text-[#F5F2EA]">
        {title}
      </h3>
      {description && (
        <p className="text-xs text-[#73766F] dark:text-[#829783] max-w-sm mt-1 mb-3">
          {description}
        </p>
      )}
      {actionLabel && onAction && (
        <Button variant="outline" size="sm" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  )
}
