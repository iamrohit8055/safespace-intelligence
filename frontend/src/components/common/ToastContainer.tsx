import React from 'react'
import { CheckCircle2, AlertCircle, Info, XCircle, X } from 'lucide-react'
import { useUIStore } from '../../stores/ui.store'
import { cn } from '../../lib/utils'

export const ToastContainer: React.FC = () => {
  const { toasts, removeToast } = useUIStore()

  if (toasts.length === 0) return null

  return (
    <aside
      aria-label="System notifications"
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none"
    >
      {toasts.map((toast) => {
        const icons = {
          success: <CheckCircle2 className="h-5 w-5 text-emerald-500 shrink-0" />,
          error: <XCircle className="h-5 w-5 text-rose-500 shrink-0" />,
          info: <Info className="h-5 w-5 text-sky-500 shrink-0" />,
          warning: <AlertCircle className="h-5 w-5 text-amber-500 shrink-0" />,
        }

        return (
          <div
            key={toast.id}
            role="status"
            className={cn(
              'pointer-events-auto flex items-start gap-3 p-4 rounded-xl border shadow-lg transition-all animate-in slide-in-from-bottom-2',
              'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 text-slate-900 dark:text-slate-100'
            )}
          >
            {icons[toast.type]}
            <div className="flex-1 min-w-0">
              <h4 className="text-xs font-semibold leading-tight">{toast.title}</h4>
              {toast.message && (
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 break-words">
                  {toast.message}
                </p>
              )}
            </div>
            <button
              type="button"
              onClick={() => removeToast(toast.id)}
              className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-0.5 rounded-sm"
              aria-label="Dismiss toast"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )
      })}
    </aside>
  )
}
