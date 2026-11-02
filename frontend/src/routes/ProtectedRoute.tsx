import React from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuthStore } from '../stores/auth.store'
import type { RoleType } from '../types'

export interface ProtectedRouteProps {
  allowedRoles?: RoleType[]
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ allowedRoles }) => {
  const { isAuthenticated, user } = useAuthStore()
  const location = useLocation()

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (allowedRoles && allowedRoles.length > 0) {
    const hasRole = user.roles.some((role) => allowedRoles.includes(role))
    if (!hasRole) {
      // Redirect to default home page based on user's actual role
      if (user.roles.includes('admin')) {
        return <Navigate to="/admin" replace />
      }
      if (user.roles.includes('verifier')) {
        return <Navigate to="/verifier/queue" replace />
      }
      if (user.roles.includes('maintenance')) {
        return <Navigate to="/maintenance/tasks" replace />
      }
      return <Navigate to="/citizen" replace />
    }
  }

  return <Outlet />
}
