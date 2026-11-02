import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '../stores/auth.store'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor: attach bearer token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (!config.headers.Authorization) {
      const token = useAuthStore.getState().token || localStorage.getItem('safespace_token')
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor: handle 401 unauthorized & normalize errors
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string | Array<{ msg: string }> }>) => {
    if (error.response?.status === 401) {
      const currentPath = window.location.pathname
      if (!currentPath.startsWith('/login') && !currentPath.startsWith('/register')) {
        useAuthStore.getState().logout()
        window.location.href = `/login?redirect=${encodeURIComponent(currentPath)}`
      }
    }

    // Extract human-readable error detail
    let message = 'An unexpected network error occurred'
    if (error.response?.data?.detail) {
      const detail = error.response.data.detail
      if (typeof detail === 'string') {
        message = detail
      } else if (Array.isArray(detail) && detail.length > 0 && detail[0].msg) {
        message = detail.map((d) => d.msg).join(', ')
      }
    } else if (error.message) {
      message = error.message
    }

    const enhancedError = new Error(message)
    return Promise.reject(enhancedError)
  }
)
