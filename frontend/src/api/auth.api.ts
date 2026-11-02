import { apiClient } from './client'
import type { TokenResponse, User } from '../types'

export interface LoginPayload {
  email: string
  password: string
}

export interface RegisterPayload {
  email: string
  password: string
  full_name: string
}

export const authApi = {
  login: async (payload: LoginPayload): Promise<TokenResponse> => {
    const res = await apiClient.post<TokenResponse>('/auth/login', payload)
    return res.data
  },

  register: async (payload: RegisterPayload): Promise<User> => {
    const res = await apiClient.post<User>('/auth/register', payload)
    return res.data
  },

  getMe: async (customToken?: string): Promise<User> => {
    const headers = customToken ? { Authorization: `Bearer ${customToken}` } : {}
    const res = await apiClient.get<User>('/auth/me', { headers })
    return res.data
  },
}
