import React from 'react'
import { cn } from '../../lib/utils'

export const Table: React.FC<React.TableHTMLAttributes<HTMLTableElement>> = ({
  className,
  children,
  ...props
}) => {
  return (
    <div className="relative w-full overflow-x-auto rounded-sm border border-[#829783]/30 dark:border-[#829783]/20 bg-[#FFFEFA] dark:bg-[#1E211E]">
      <table
        className={cn('w-full caption-bottom text-xs text-left', className)}
        {...props}
      >
        {children}
      </table>
    </div>
  )
}

export const TableHeader: React.FC<React.HTMLAttributes<HTMLTableSectionElement>> = ({
  className,
  children,
  ...props
}) => {
  return (
    <thead
      className={cn(
        'bg-[#F5F2EA]/80 dark:bg-[#18372C]/30 text-[10px] font-mono uppercase tracking-wider text-[#73766F] dark:text-[#829783] border-b border-[#DCE5D9]/80 dark:border-[#829783]/20 select-none',
        className
      )}
      {...props}
    >
      {children}
    </thead>
  )
}

export const TableBody: React.FC<React.HTMLAttributes<HTMLTableSectionElement>> = ({
  className,
  children,
  ...props
}) => {
  return (
    <tbody
      className={cn('divide-y divide-[#DCE5D9]/50 dark:divide-[#829783]/15', className)}
      {...props}
    >
      {children}
    </tbody>
  )
}

export const TableRow: React.FC<React.HTMLAttributes<HTMLTableRowElement>> = ({
  className,
  children,
  ...props
}) => {
  return (
    <tr
      className={cn(
        'transition-colors hover:bg-[#F5F2EA]/50 dark:hover:bg-[#18372C]/20 data-[state=selected]:bg-[#DCE5D9]/30',
        className
      )}
      {...props}
    >
      {children}
    </tr>
  )
}

export const TableHead: React.FC<React.ThHTMLAttributes<HTMLTableCellElement>> = ({
  className,
  children,
  ...props
}) => {
  return (
    <th
      className={cn(
        'h-8 px-3 text-left font-medium align-middle text-[#18372C] dark:text-[#DCE5D9]',
        className
      )}
      {...props}
    >
      {children}
    </th>
  )
}

export const TableCell: React.FC<React.TdHTMLAttributes<HTMLTableCellElement>> = ({
  className,
  children,
  ...props
}) => {
  return (
    <td
      className={cn(
        'py-2.5 px-3 align-middle text-[#292D29] dark:text-[#F5F2EA]',
        className
      )}
      {...props}
    >
      {children}
    </td>
  )
}
