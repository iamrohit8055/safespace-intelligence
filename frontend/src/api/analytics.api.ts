import { apiClient } from './client'
import type {
  AnalyticsOverviewResponse,
  ReportAnalyticsResponse,
  SdiAnalyticsResponse,
  ConfidenceAnalyticsResponse,
  MaintenanceAnalyticsResponse,
  TrendsAnalyticsResponse,
} from '../types'

export const analyticsApi = {
  getOverview: async (): Promise<AnalyticsOverviewResponse> => {
    const response = await apiClient.get<AnalyticsOverviewResponse>(
      '/admin/analytics/overview'
    )
    return response.data
  },

  getReportsAnalytics: async (params?: {
    start_date?: string
    end_date?: string
    area_id?: string
  }): Promise<ReportAnalyticsResponse> => {
    const response = await apiClient.get<ReportAnalyticsResponse>(
      '/admin/analytics/reports',
      { params }
    )
    return response.data
  },

  getSdiAnalytics: async (params?: {
    area_id?: string
  }): Promise<SdiAnalyticsResponse> => {
    const response = await apiClient.get<SdiAnalyticsResponse>(
      '/admin/analytics/sdi',
      { params }
    )
    return response.data
  },

  getConfidenceAnalytics: async (params?: {
    area_id?: string
  }): Promise<ConfidenceAnalyticsResponse> => {
    const response = await apiClient.get<ConfidenceAnalyticsResponse>(
      '/admin/analytics/confidence',
      { params }
    )
    return response.data
  },

  getMaintenanceAnalytics: async (params?: {
    start_date?: string
    end_date?: string
    technician_id?: string
  }): Promise<MaintenanceAnalyticsResponse> => {
    const response = await apiClient.get<MaintenanceAnalyticsResponse>(
      '/admin/analytics/maintenance',
      { params }
    )
    return response.data
  },

  getTrendsAnalytics: async (params?: {
    start_date?: string
    end_date?: string
    area_id?: string
  }): Promise<TrendsAnalyticsResponse> => {
    const response = await apiClient.get<TrendsAnalyticsResponse>(
      '/admin/analytics/trends',
      { params }
    )
    return response.data
  },
}
