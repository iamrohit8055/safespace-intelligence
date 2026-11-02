import React, { useEffect } from 'react'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AppRoutes } from './routes/AppRoutes'
import { useAuthStore } from './stores/auth.store'
import { useUIStore } from './stores/ui.store'
import { authApi } from './api/auth.api'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 5000,
    },
  },
})

export function App() {
  const { token, setUser, logout } = useAuthStore()
  const { theme } = useUIStore()

  // Apply dark mode class to <html>
  useEffect(() => {
    const root = document.documentElement
    if (theme === 'dark') {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }
  }, [theme])

  // Restore authenticated user session on mount
  useEffect(() => {
    if (token) {
      authApi
        .getMe()
        .then((user) => setUser(user))
        .catch((err) => {
          console.warn('Session expired or token invalid:', err)
          logout()
        })
    }
  }, [token, setUser, logout])

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
