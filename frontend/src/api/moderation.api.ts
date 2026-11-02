import { apiClient } from './client'
import type {
  Report,
  ReportListResponse,
  VerifyReportRequest,
  RejectReportRequest,
  ReopenReportRequest,
} from '../types'

export const moderationApi = {
  // List reports with filters for moderation
  listReports: async (params?: {
    status?: string
    category_id?: number
    limit?: number
    offset?: number
  }): Promise<ReportListResponse> => {
    const response = await apiClient.get<ReportListResponse>('/admin/reports', { params })
    return response.data
  },

  // Get single report detail for staff review
  getReportDetail: async (reportId: string): Promise<Report> => {
    const response = await apiClient.get<Report>(`/admin/reports/detail/${reportId}`)
    return response.data
  },

  // Get pending queue (FIFO)
  getPendingQueue: async (params?: { limit?: number; offset?: number }): Promise<ReportListResponse> => {
    const response = await apiClient.get<ReportListResponse>('/admin/reports/pending', { params })
    return response.data
  },

  // Start verification on a report
  startVerification: async (reportId: string): Promise<Report> => {
    const response = await apiClient.post<Report>(`/admin/reports/${reportId}/start-verification`)
    return response.data
  },

  // Approve and verify report with physical deficiency severity (1-5)
  verifyReport: async (
    reportId: string,
    payload: VerifyReportRequest & { verified_severity?: number; verification_notes?: string }
  ): Promise<Report> => {
    const formatted = {
      verified_severity: payload.verified_severity ?? payload.severity,
      verification_notes: payload.verification_notes ?? payload.notes,
    }
    const response = await apiClient.post<Report>(`/admin/reports/${reportId}/verify`, formatted)
    return response.data
  },

  // Reject report with categorical reason
  rejectReport: async (
    reportId: string,
    payload: RejectReportRequest & { verification_notes?: string }
  ): Promise<Report> => {
    const formatted = {
      rejection_reason: payload.rejection_reason,
      verification_notes: payload.verification_notes ?? payload.notes,
    }
    const response = await apiClient.post<Report>(`/admin/reports/${reportId}/reject`, formatted)
    return response.data
  },

  // Reopen report back to UNDER_VERIFICATION
  reopenReport: async (reportId: string, payload: ReopenReportRequest): Promise<Report> => {
    const response = await apiClient.post<Report>(`/admin/reports/${reportId}/reopen`, payload)
    return response.data
  },
}
