import { apiClient } from './client'
import type {
  DuplicateCandidate,
  DuplicateCandidateListResponse,
  DuplicateReviewRequest,
  DuplicateReviewHistoryResponse,
} from '../types'

export const duplicatesApi = {
  // List duplicate candidate pairs
  listCandidates: async (params?: {
    review_status?: string
    limit?: number
    offset?: number
  }): Promise<DuplicateCandidateListResponse> => {
    const response = await apiClient.get<DuplicateCandidateListResponse>(
      '/admin/intelligence/duplicate-candidates',
      { params }
    )
    return response.data
  },

  // Get duplicate candidates for a specific report
  getCandidatesForReport: async (
    reportId: string,
    detect = true
  ): Promise<DuplicateCandidate[]> => {
    const response = await apiClient.get<DuplicateCandidate[]>(
      `/admin/intelligence/reports/${reportId}/duplicate-candidates`,
      { params: { detect } }
    )
    return response.data
  },

  // Trigger batch duplicate detection
  triggerDetection: async (params?: {
    administrative_area_id?: string
    configuration_version?: string
  }): Promise<{
    candidates_evaluated: number
    new_candidates_created: number
    configuration_version: string
    administrative_area_id?: string | null
  }> => {
    const response = await apiClient.post(
      '/admin/intelligence/duplicate-candidates/detect',
      params || {}
    )
    return response.data
  },

  // Review a duplicate candidate pair
  reviewCandidate: async (
    candidateId: string,
    payload: DuplicateReviewRequest
  ): Promise<DuplicateCandidate> => {
    const response = await apiClient.post<DuplicateCandidate>(
      `/admin/intelligence/duplicate-candidates/${candidateId}/review`,
      payload
    )
    return response.data
  },

  // Get duplicate review history for a report
  getDuplicateHistory: async (
    reportId: string
  ): Promise<DuplicateReviewHistoryResponse[]> => {
    const response = await apiClient.get<DuplicateReviewHistoryResponse[]>(
      `/admin/intelligence/reports/${reportId}/duplicate-history`
    )
    return response.data
  },
}
