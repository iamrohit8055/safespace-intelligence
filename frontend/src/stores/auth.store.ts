import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { RoleType, User } from '../types'

interface AuthState {
  token: string | null
  user: User | null
  activeRole: RoleType | null
  isAuthenticated: boolean
  setAuth: (token: string, user: User) => void
  setUser: (user: User) => void
  setActiveRole: (role: RoleType) => void
  logout: () => void
  hasRole: (role: RoleType) => boolean
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      activeRole: null,
      isAuthenticated: false,

      setAuth: (token: string, user: User) => {
        // Derive initial active role based on user roles
        const initialRole: RoleType = user.roles.includes('admin')
          ? 'admin'
          : user.roles.includes('verifier')
          ? 'verifier'
          : user.roles.includes('maintenance')
          ? 'maintenance'
          : 'citizen'

        set({
          token,
          user,
          activeRole: initialRole,
          isAuthenticated: true,
        })
      },

      setUser: (user: User) => {
        set((state) => ({
          user,
          activeRole: state.activeRole || user.roles[0] || 'citizen',
        }))
      },

      setActiveRole: (role: RoleType) => {
        const user = get().user
        if (user && user.roles.includes(role)) {
          set({ activeRole: role })
        }
      },

      logout: () => {
        try {
          localStorage.removeItem('safespace_token')
        } catch {
          // ignore in environments without localStorage
        }
        set({
          token: null,
          user: null,
          activeRole: null,
          isAuthenticated: false,
        })
      },

      hasRole: (role: RoleType) => {
        const user = get().user
        if (!user) return false
        return user.roles.includes(role)
      },
    }),
    {
      name: 'safespace_auth',
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        activeRole: state.activeRole,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)
