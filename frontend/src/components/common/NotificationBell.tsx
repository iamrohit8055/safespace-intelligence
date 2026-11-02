import React, { useState, useRef, useEffect } from 'react'
import { Bell, CheckCheck, Clock } from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { notificationsApi } from '../../api/notifications.api'
import { formatRelativeDays } from '../../lib/utils'

export const NotificationBell: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const queryClient = useQueryClient()

  // Polling unread count every 30 seconds
  const { data: countData } = useQuery({
    queryKey: ['notifications', 'unread-count'],
    queryFn: notificationsApi.getUnreadCount,
    refetchInterval: 30000,
  })

  const { data: notificationsData } = useQuery({
    queryKey: ['notifications', 'list'],
    queryFn: () => notificationsApi.getMyNotifications({ limit: 10 }),
    enabled: isOpen,
  })

  const markAllMutation = useMutation({
    mutationFn: notificationsApi.markAllAsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
    },
  })

  const markSingleMutation = useMutation({
    mutationFn: (id: string) => notificationsApi.markAsRead(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
    },
  })

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  const unreadCount = countData?.unread_count || 0

  return (
    <div className="relative" ref={menuRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-1.5 rounded-md text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
        aria-label={`Notifications, ${unreadCount} unread`}
      >
        <Bell className="h-4 w-4" />
        {unreadCount > 0 && (
          <span className="absolute top-1 right-1 flex h-3.5 min-w-3.5 px-0.5 items-center justify-center rounded-full bg-rose-500 text-[9px] font-mono font-bold text-white shadow-2xs">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-1.5 w-80 sm:w-96 rounded-md border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-lg z-50 overflow-hidden text-slate-900 dark:text-slate-100 animate-in fade-in-50">
          <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 px-3 py-2 bg-slate-50/80 dark:bg-slate-950/40">
            <div className="flex items-center gap-1.5">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-300">
                System Alerts
              </span>
              {unreadCount > 0 && (
                <span className="px-1.5 py-0.2 rounded-xs bg-rose-100 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 text-[10px] font-mono font-medium">
                  {unreadCount} new
                </span>
              )}
            </div>
            {unreadCount > 0 && (
              <button
                type="button"
                onClick={() => markAllMutation.mutate()}
                className="text-[11px] text-sky-600 dark:text-sky-400 hover:underline inline-flex items-center gap-1 font-medium cursor-pointer"
              >
                <CheckCheck className="h-3 w-3" /> Mark all read
              </button>
            )}
          </div>

          <div className="max-h-72 overflow-y-auto divide-y divide-slate-100 dark:divide-slate-800/60">
            {notificationsData?.items && notificationsData.items.length > 0 ? (
              notificationsData.items.map((item) => (
                <div
                  key={item.id}
                  onClick={() => {
                    if (!item.is_read) {
                      markSingleMutation.mutate(item.id)
                    }
                  }}
                  className={`p-3 text-xs transition-colors cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/40 ${
                    !item.is_read ? 'bg-sky-50/40 dark:bg-sky-950/15' : ''
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-medium text-slate-900 dark:text-slate-100 leading-snug">
                      {item.title}
                    </span>
                    <span className="text-[10px] font-mono text-slate-400 shrink-0 inline-flex items-center gap-1">
                      <Clock className="h-2.5 w-2.5" />
                      {formatRelativeDays(item.created_at)}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1 line-clamp-2 leading-relaxed">
                    {item.message}
                  </p>
                </div>
              ))
            ) : (
              <div className="p-6 text-center text-xs text-slate-400">
                No recent notifications or alerts.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
