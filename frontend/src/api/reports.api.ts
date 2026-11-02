import { apiClient } from './client'
import type {
  PublicMapItem,
  Report,
  ReportCategory,
  ReportMedia,
  VerificationHistoryItem,
} from '../types'

export interface CreateReportPayload {
  category_id?: number
  category_code?: string
  title: string
  description: string
  latitude: number
  longitude: number
  address_text?: string
  observed_at?: string
}

export interface PaginatedList<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export const reportsApi = {
  getCategories: async (): Promise<ReportCategory[]> => {
    const res = await apiClient.get<ReportCategory[]>('/reports/categories')
    return res.data
  },

  getPublicMap: async (params?: { category_id?: number; status?: string; limit?: number }): Promise<PublicMapItem[]> => {
    const res = await apiClient.get<PublicMapItem[]>('/reports/public/map', { params })
    return res.data
  },

  getPublicMapReports: async (params?: { category_id?: number; status?: string; limit?: number }): Promise<PublicMapItem[]> => {
    const res = await apiClient.get<PublicMapItem[]>('/reports/public/map', { params })
    return res.data
  },

  submitReport: async (payload: CreateReportPayload): Promise<Report> => {
    const res = await apiClient.post<Report>('/reports', payload)
    return res.data
  },

  createReport: async (payload: CreateReportPayload): Promise<Report> => {
    const res = await apiClient.post<Report>('/reports', payload)
    return res.data
  },

  listMyReports: async (params?: { status?: string; limit?: number; offset?: number }): Promise<PaginatedList<Report>> => {
    const res = await apiClient.get<PaginatedList<Report>>('/reports', { params })
    return res.data
  },

  getMyReports: async (params?: { status?: string; limit?: number; offset?: number }): Promise<PaginatedList<Report>> => {
    const res = await apiClient.get<PaginatedList<Report>>('/reports', { params })
    return res.data
  },

  getReportDetail: async (reportId: string): Promise<Report> => {
    const res = await apiClient.get<Report>(`/reports/${reportId}`)
    return res.data
  },

  getReport: async (reportId: string): Promise<Report> => {
    const res = await apiClient.get<Report>(`/reports/${reportId}`)
    return res.data
  },

  getVerificationHistory: async (reportId: string): Promise<VerificationHistoryItem[]> => {
    const res = await apiClient.get<VerificationHistoryItem[]>(`/reports/${reportId}/verification-history`)
    return res.data
  },

  uploadMedia: async (reportId: string, file: File): Promise<ReportMedia> => {
    const formData = new FormData()
    formData.append('file', file)
    const res = await apiClient.post<ReportMedia>(`/reports/${reportId}/media`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return res.data
  },

  getMediaDownloadUrl: (reportId: string, mediaId: string): string => {
    const base = import.meta.env.VITE_API_BASE_URL || '/api/v1'
    return `${base}/reports/${reportId}/media/${mediaId}`
  },
}
