import { describe, it, expect, beforeEach } from 'vitest'
import { useAuthStore } from '../stores/auth.store'
import type { User } from '../types'

describe('Auth Store & Role Access', () => {
  beforeEach(() => {
    useAuthStore.getState().logout()
  })

  it('initializes with unauthenticated state', () => {
    const state = useAuthStore.getState()
    expect(state.isAuthenticated).toBe(false)
    expect(state.user).toBeNull()
    expect(state.token).toBeNull()
  })

  it('sets authentication state correctly for citizen', () => {
    const mockUser: User = {
      id: 'usr-123',
      email: 'citizen@safespace.org',
      full_name: 'Test Citizen',
      is_active: true,
      is_verified: true,
      roles: ['citizen'],
      created_at: new Date().toISOString(),
    }

    useAuthStore.getState().setAuth('mock-token-xyz', mockUser)

    const state = useAuthStore.getState()
    expect(state.isAuthenticated).toBe(true)
    expect(state.token).toBe('mock-token-xyz')
    expect(state.user?.email).toBe('citizen@safespace.org')
    expect(state.activeRole).toBe('citizen')
    expect(useAuthStore.getState().hasRole('citizen')).toBe(true)
    expect(useAuthStore.getState().hasRole('admin')).toBe(false)
  })

  it('sets active role correctly for administrator', () => {
    const mockAdmin: User = {
      id: 'usr-admin',
      email: 'admin@safespace.org',
      full_name: 'System Admin',
      is_active: true,
      is_verified: true,
      roles: ['admin', 'citizen'],
      created_at: new Date().toISOString(),
    }

    useAuthStore.getState().setAuth('token-admin', mockAdmin)

    const state = useAuthStore.getState()
    expect(state.activeRole).toBe('admin')
    expect(useAuthStore.getState().hasRole('admin')).toBe(true)
    expect(useAuthStore.getState().hasRole('citizen')).toBe(true)
  })

  it('clears session on logout', () => {
    const mockUser: User = {
      id: 'usr-123',
      email: 'citizen@safespace.org',
      full_name: 'Citizen',
      is_active: true,
      is_verified: true,
      roles: ['citizen'],
      created_at: new Date().toISOString(),
    }

    useAuthStore.getState().setAuth('tok', mockUser)
    useAuthStore.getState().logout()

    const state = useAuthStore.getState()
    expect(state.isAuthenticated).toBe(false)
    expect(state.token).toBeNull()
    expect(state.user).toBeNull()
  })
})
