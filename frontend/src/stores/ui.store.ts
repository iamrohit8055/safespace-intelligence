import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface ToastMessage {
  id: string
  type: 'success' | 'error' | 'info' | 'warning'
  title: string
  message?: string
}

interface UIState {
  theme: 'dark' | 'light'
  sidebarCollapsed: boolean
  toasts: ToastMessage[]
  toggleTheme: () => void
  setTheme: (theme: 'dark' | 'light') => void
  toggleSidebar: () => void
  addToast: (toast: Omit<ToastMessage, 'id'>) => void
  removeToast: (id: string) => void
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      theme: 'dark',
      sidebarCollapsed: false,
      toasts: [],

      toggleTheme: () => {
        set((state) => {
          const next = state.theme === 'dark' ? 'light' : 'dark'
          if (typeof document !== 'undefined') {
            if (next === 'dark') {
              document.documentElement.classList.add('dark')
            } else {
              document.documentElement.classList.remove('dark')
            }
          }
          return { theme: next }
        })
      },

      setTheme: (theme: 'dark' | 'light') => {
        if (typeof document !== 'undefined') {
          if (theme === 'dark') {
            document.documentElement.classList.add('dark')
          } else {
            document.documentElement.classList.remove('dark')
          }
        }
        set({ theme })
      },

      toggleSidebar: () => {
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed }))
      },

      addToast: (toast) => {
        const id = Math.random().toString(36).substring(2, 9)
        set((state) => ({ toasts: [...state.toasts, { ...toast, id }] }))
        setTimeout(() => {
          set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }))
        }, 5000)
      },

      removeToast: (id: string) => {
        set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }))
      },
    }),
    {
      name: 'safespace_ui',
      partialize: (state) => ({
        theme: state.theme,
        sidebarCollapsed: state.sidebarCollapsed,
      }),
    }
  )
)
