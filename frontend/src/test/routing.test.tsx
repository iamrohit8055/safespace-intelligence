import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import React from 'react'
import { ProtectedRoute } from '../routes/ProtectedRoute'
import { useAuthStore } from '../stores/auth.store'
import type { User } from '../types'

describe('ProtectedRoute Role Enforcement', () => {
  beforeEach(() => {
    useAuthStore.getState().logout()
  })

  it('redirects unauthenticated users to login page', () => {
    render(
      <MemoryRouter initialEntries={['/admin']}>
        <Routes>
          <Route path="/login" element={<div>Login Page Screen</div>} />
          <Route element={<ProtectedRoute allowedRoles={['admin']} />}>
            <Route path="/admin" element={<div>Protected Admin Dashboard</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByText('Login Page Screen')).toBeInTheDocument()
    expect(screen.queryByText('Protected Admin Dashboard')).not.toBeInTheDocument()
  })

  it('allows authorized users into role page', () => {
    const adminUser: User = {
      id: 'admin-1',
      email: 'admin@safespace.org',
      full_name: 'Admin User',
      is_active: true,
      is_verified: true,
      roles: ['admin'],
      created_at: new Date().toISOString(),
    }
    useAuthStore.getState().setAuth('admin-token', adminUser)

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <Routes>
          <Route path="/login" element={<div>Login Page Screen</div>} />
          <Route element={<ProtectedRoute allowedRoles={['admin']} />}>
            <Route path="/admin" element={<div>Protected Admin Dashboard</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByText('Protected Admin Dashboard')).toBeInTheDocument()
  })

  it('redirects unauthorized roles away from restricted sections', () => {
    const citizenUser: User = {
      id: 'citizen-1',
      email: 'citizen@safespace.org',
      full_name: 'Citizen User',
      is_active: true,
      is_verified: true,
      roles: ['citizen'],
      created_at: new Date().toISOString(),
    }
    useAuthStore.getState().setAuth('citizen-token', citizenUser)

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <Routes>
          <Route path="/citizen" element={<div>Citizen Portal Home</div>} />
          <Route element={<ProtectedRoute allowedRoles={['admin']} />}>
            <Route path="/admin" element={<div>Protected Admin Dashboard</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    )

    // Should redirect citizen away from admin to their portal home
    expect(screen.getByText('Citizen Portal Home')).toBeInTheDocument()
    expect(screen.queryByText('Protected Admin Dashboard')).not.toBeInTheDocument()
  })
})
