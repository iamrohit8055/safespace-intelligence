import { apiClient } from './client'
import type {
  AreaScore,
  GeoJSONAreaCollection,
  ScoringConfiguration,
} from '../types'

export const intelligenceApi = {
  // Get GeoJSON boundaries of all areas with attached SDI, priority, confidence scores
  getAreasGeoJSON: async (): Promise<GeoJSONAreaCollection> => {
    const response = await apiClient.get<GeoJSONAreaCollection>(
      '/admin/intelligence/areas/geojson'
    )
    return response.data
  },

  // List scoring configurations
  getScoringConfigurations: async (): Promise<ScoringConfiguration[]> => {
    const response = await apiClient.get<ScoringConfiguration[]>(
      '/admin/intelligence/scoring-configurations'
    )
    return response.data
  },

  // Calculate SDI for an area
  calculateAreaSDI: async (
    areaId: string,
    params?: { version?: string; min_completeness_pct?: number }
  ): Promise<AreaScore> => {
    const response = await apiClient.post<AreaScore>(
      `/admin/intelligence/areas/${areaId}/calculate`,
      null,
      { params }
    )
    return response.data
  },

  // Get current SDI for an area
  getAreaSDI: async (areaId: string): Promise<AreaScore> => {
    const response = await apiClient.get<AreaScore>(
      `/admin/intelligence/areas/${areaId}/sdi`
    )
    return response.data
  },

  // Get SDI history for an area
  getAreaSDIHistory: async (
    areaId: string,
    params?: { limit?: number; offset?: number }
  ): Promise<AreaScore[]> => {
    const response = await apiClient.get<AreaScore[]>(
      `/admin/intelligence/areas/${areaId}/sdi-history`,
      { params }
    )
    return response.data
  },

  // Calculate area confidence
  calculateAreaConfidence: async (
    areaId: string,
    version?: string
  ): Promise<any> => {
    const response = await apiClient.post(
      `/admin/intelligence/areas/${areaId}/calculate-confidence`,
      null,
      { params: { version } }
    )
    return response.data
  },

  // Get area confidence
  getAreaConfidence: async (areaId: string): Promise<any> => {
    const response = await apiClient.get(
      `/admin/intelligence/areas/${areaId}/confidence`
    )
    return response.data
  },

  // Get area confidence history
  getAreaConfidenceHistory: async (
    areaId: string,
    params?: { limit?: number; offset?: number }
  ): Promise<any[]> => {
    const response = await apiClient.get(
      `/admin/intelligence/areas/${areaId}/confidence-history`,
      { params }
    )
    return response.data
  },

  // Get report confidence
  getReportConfidence: async (reportId: string): Promise<any> => {
    const response = await apiClient.get(
      `/admin/intelligence/reports/${reportId}/confidence`
    )
    return response.data
  },
}
