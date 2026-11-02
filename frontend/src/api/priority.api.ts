import { apiClient } from './client'
import type {
  AreaPriorityScore,
  AreaPriorityListResponse,
} from '../types'

export const priorityApi = {
  // List inspection priority configurations
  getPriorityConfigurations: async (): Promise<any[]> => {
    const response = await apiClient.get<any[]>(
      '/admin/intelligence/priority/configurations'
    )
    return response.data
  },

  // Calculate area inspection priority
  calculateAreaPriority: async (
    areaId: string,
    version?: string
  ): Promise<AreaPriorityScore> => {
    const response = await apiClient.post<AreaPriorityScore>(
      `/admin/intelligence/areas/${areaId}/calculate-priority`,
      null,
      { params: { version } }
    )
    return response.data
  },

  // Get current priority for area
  getAreaPriority: async (areaId: string): Promise<AreaPriorityScore> => {
    const response = await apiClient.get<AreaPriorityScore>(
      `/admin/intelligence/areas/${areaId}/priority`
    )
    return response.data
  },

  // Get priority calculation history for an area
  getAreaPriorityHistory: async (
    areaId: string,
    params?: { limit?: number; offset?: number }
  ): Promise<AreaPriorityScore[]> => {
    const response = await apiClient.get<AreaPriorityScore[]>(
      `/admin/intelligence/areas/${areaId}/priority-history`,
      { params }
    )
    return response.data
  },

  // List ranked area inspection priorities with filtering
  listAreaPriorities: async (params?: {
    priority_level?: string
    area_type?: string
    sort_by?: string
    limit?: number
    offset?: number
  }): Promise<AreaPriorityListResponse> => {
    const response = await apiClient.get<AreaPriorityListResponse>(
      '/admin/intelligence/priority/areas',
      { params }
    )
    return response.data
  },
}
