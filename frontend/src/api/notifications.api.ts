import { apiClient } from './client'
import type { NotificationListResponse } from '../types'

export const notificationsApi = {
  getMyNotifications: async (params?: {
    unread_only?: boolean
    limit?: number
    offset?: number
  }): Promise<NotificationListResponse> => {
    const response = await apiClient.get<NotificationListResponse>(
      '/notifications',
      { params }
    )
    return response.data
  },

  getUnreadCount: async (): Promise<{ unread_count: number }> => {
    const response = await apiClient.get<{ unread_count: number }>(
      '/notifications/unread-count'
    )
    return response.data
  },

  markAsRead: async (notificationId: string): Promise<any> => {
    const response = await apiClient.post(
      `/notifications/${notificationId}/read`
    )
    return response.data
  },

  markAllAsRead: async (): Promise<any> => {
    const response = await apiClient.post('/notifications/read-all')
    return response.data
  },
}
