import { apiClient } from './client'
import type {
  MaintenanceTask,
  MaintenanceTaskListResponse,
  TechnicianSummary,
  MaintenanceTaskEvent,
} from '../types'

export const maintenanceApi = {
  // --- Technician Endpoints ---
  getMyTasks: async (params?: {
    status?: string
    priority?: string
    limit?: number
    offset?: number
  }): Promise<MaintenanceTaskListResponse> => {
    const response = await apiClient.get<MaintenanceTaskListResponse>(
      '/maintenance/tasks/my',
      { params }
    )
    return response.data
  },

  acceptTask: async (taskId: string, notes?: string): Promise<MaintenanceTask> => {
    const response = await apiClient.post<MaintenanceTask>(
      `/maintenance/tasks/${taskId}/accept`,
      notes ? { notes } : {}
    )
    return response.data
  },

  startTask: async (taskId: string, notes?: string): Promise<MaintenanceTask> => {
    const response = await apiClient.post<MaintenanceTask>(
      `/maintenance/tasks/${taskId}/start`,
      notes ? { notes } : {}
    )
    return response.data
  },

  blockTask: async (taskId: string, notes: string): Promise<MaintenanceTask> => {
    const response = await apiClient.post<MaintenanceTask>(
      `/maintenance/tasks/${taskId}/block`,
      { notes }
    )
    return response.data
  },

  completeTask: async (taskId: string, notes?: string): Promise<MaintenanceTask> => {
    const response = await apiClient.post<MaintenanceTask>(
      `/maintenance/tasks/${taskId}/complete`,
      notes ? { notes } : {}
    )
    return response.data
  },

  // --- Admin Endpoints ---
  listTechnicians: async (): Promise<TechnicianSummary[]> => {
    const response = await apiClient.get<TechnicianSummary[]>(
      '/admin/maintenance/technicians'
    )
    return response.data
  },

  listTasks: async (params?: {
    status?: string
    priority?: string
    assigned_to_id?: string
    report_id?: string
    limit?: number
    offset?: number
  }): Promise<MaintenanceTaskListResponse> => {
    const response = await apiClient.get<MaintenanceTaskListResponse>(
      '/admin/maintenance/tasks',
      { params }
    )
    return response.data
  },

  createTask: async (payload: {
    report_id: string
    title: string
    description?: string
    priority?: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
    assigned_to_id?: string
    assigned_to_user_id?: string
    allow_duplicate?: boolean
    duplicate_override_reason?: string
  }): Promise<MaintenanceTask> => {
    const formattedPayload = {
      ...payload,
      assigned_to_user_id: payload.assigned_to_user_id || payload.assigned_to_id,
    }
    const response = await apiClient.post<MaintenanceTask>(
      '/admin/maintenance/tasks',
      formattedPayload
    )
    return response.data
  },

  getTask: async (taskId: string): Promise<MaintenanceTask> => {
    const response = await apiClient.get<MaintenanceTask>(
      `/admin/maintenance/tasks/${taskId}`
    )
    return response.data
  },

  assignTask: async (
    taskId: string,
    assignedToId: string,
    notes?: string
  ): Promise<MaintenanceTask> => {
    const response = await apiClient.post<MaintenanceTask>(
      `/admin/maintenance/tasks/${taskId}/assign`,
      { assigned_to_id: assignedToId, notes }
    )
    return response.data
  },

  cancelTask: async (taskId: string, notes: string): Promise<MaintenanceTask> => {
    const response = await apiClient.post<MaintenanceTask>(
      `/admin/maintenance/tasks/${taskId}/cancel`,
      { notes }
    )
    return response.data
  },

  getTaskHistory: async (taskId: string): Promise<MaintenanceTaskEvent[]> => {
    const response = await apiClient.get<MaintenanceTaskEvent[]>(
      `/admin/maintenance/tasks/${taskId}/history`
    )
    return response.data
  },
}
