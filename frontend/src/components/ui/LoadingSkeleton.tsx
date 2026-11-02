import React from 'react'
import { cn } from '../../lib/utils'

export const Skeleton: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className,
  ...props
}) => {
  return (
    <div
      className={cn(
        'animate-pulse rounded-xs bg-slate-200/80 dark:bg-slate-800/80',
        className
      )}
      {...props}
    />
  )
}

export const TableSkeleton: React.FC<{ rows?: number }> = ({ rows = 5 }) => {
  return (
    <div className="space-y-1.5 w-full">
      <Skeleton className="h-8 w-full rounded-md" />
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full rounded-md" />
      ))}
    </div>
  )
}

export const CardSkeleton: React.FC = () => {
  return (
    <div className="p-4 rounded-md border border-slate-200 dark:border-slate-800/80 space-y-2">
      <Skeleton className="h-3 w-1/3" />
      <Skeleton className="h-7 w-1/2" />
      <Skeleton className="h-3 w-2/3" />
    </div>
  )
}
