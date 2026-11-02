import React, { useEffect, useRef } from 'react'
import { X } from 'lucide-react'
import { cn } from '../../lib/utils'

export interface ModalProps {
  isOpen: boolean
  onClose: () => void
  title: string
  description?: string
  children: React.ReactNode
  size?: 'sm' | 'md' | 'lg' | 'xl'
}

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  description,
  children,
  size = 'md',
}) => {
  const dialogRef = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return

    if (isOpen) {
      if (!dialog.open) {
        dialog.showModal()
      }
    } else {
      if (dialog.open) {
        dialog.close()
      }
    }
  }, [isOpen])

  const handleCancel = (e: React.SyntheticEvent) => {
    e.preventDefault()
    onClose()
  }

  const handleBackdropClick = (e: React.MouseEvent<HTMLDialogElement>) => {
    if (e.target === dialogRef.current) {
      onClose()
    }
  }

  const sizeClasses = {
    sm: 'max-w-md',
    md: 'max-w-lg',
    lg: 'max-w-2xl',
    xl: 'max-w-4xl',
  }

  if (!isOpen) return null

  return (
    <dialog
      ref={dialogRef}
      onCancel={handleCancel}
      onClick={handleBackdropClick}
      className={cn(
        'w-full rounded-sm border border-[#829783]/30 dark:border-[#829783]/20 bg-[#FFFEFA] dark:bg-[#1E211E] text-[#292D29] dark:text-[#F5F2EA] p-0 shadow-xl backdrop:bg-[#18372C]/65 backdrop:backdrop-blur-xs overscroll-contain transition-all m-auto',
        sizeClasses[size]
      )}
      aria-labelledby="dialog-title"
    >
      <div className="flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#DCE5D9]/60 dark:border-[#829783]/20 px-4 py-3 bg-[#F5F2EA]/40 dark:bg-[#18372C]/20">
          <div>
            <h2 id="dialog-title" className="text-sm font-semibold tracking-tight text-[#18372C] dark:text-[#F5F2EA]">
              {title}
            </h2>
            {description && (
              <p className="text-xs text-[#73766F] dark:text-[#829783] mt-0.5">
                {description}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-xs p-1 text-[#73766F] hover:text-[#292D29] dark:hover:text-[#F5F2EA] hover:bg-[#DCE5D9]/40 dark:hover:bg-[#1F221F] transition-colors cursor-pointer"
            aria-label="Close dialog"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 overflow-y-auto overscroll-contain flex-1">
          {children}
        </div>
      </div>
    </dialog>
  )
}
