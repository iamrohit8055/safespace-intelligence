// Common and domain types for SafeSpace Intelligence

export type RoleType = 'citizen' | 'verifier' | 'maintenance' | 'admin'

export interface User {
  id: string
  email: string
  full_name: string
  is_active: boolean
  is_verified: boolean
  roles: RoleType[]
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface ReportCategory {
  id: number
  code: string
  name: string
  description: string
  is_active?: boolean
}

export interface AdministrativeAreaSummary {
  id: string
  name: string
  code: string
  area_type: string
}

export interface ReportMedia {
  id: string
  report_id: string
  mime_type: string
  file_size_bytes: number
  checksum_sha256: string
  width?: number | null
  height?: number | null
  technical_metadata?: Record<string, unknown>
  created_at: string
  download_url?: string
}

export interface Report {
  id: string
  reporter_id: string
  category: ReportCategory
  administrative_area?: AdministrativeAreaSummary | null
  title: string
  description: string
  latitude: number
  longitude: number
  address_text?: string | null
  status: 'SUBMITTED' | 'UNDER_VERIFICATION' | 'VERIFIED' | 'REJECTED' | 'ARCHIVED'
  observed_at: string
  submitted_at: string
  updated_at?: string
  media?: ReportMedia[]
  verified_severity?: number | null
  rejection_reason?: string | null
  verification_notes?: string | null
}

export interface ReportListResponse {
  items: Report[]
  total: number
  limit: number
  offset: number
}

export interface PublicMapItem {
  id: string
  title: string
  description: string
  category_id: number
  category_code: string
  category_name: string
  status: string
  latitude: number
  longitude: number
  observed_at: string
  submitted_at: string
  administrative_area_name?: string | null
  has_media?: boolean
}

export interface VerificationHistoryItem {
  id: string
  report_id: string
  verifier_id: string
  verifier_name: string
  decision: 'VERIFIED' | 'REJECTED' | 'FLAGGED' | 'MARKED_DUPLICATE'
  verified_severity?: number | null
  rejection_reason?: string | null
  verification_notes?: string | null
  verified_at: string
}

export interface VerifyReportRequest {
  severity: number
  notes?: string
}

export interface RejectReportRequest {
  rejection_reason: string
  notes?: string
}

export interface ReopenReportRequest {
  reason: string
}

export interface DuplicateCandidate {
  id: string
  first_report_id: string
  second_report_id: string
  distance_metres: number
  time_difference_seconds: number
  rule_version: string
  review_status: 'PENDING' | 'CONFIRMED_DUPLICATE' | 'NOT_DUPLICATE' | 'NEEDS_REVIEW'
  reviewer_id?: string | null
  reviewed_at?: string | null
  review_reason?: string | null
  detected_at: string
  first_report?: Report
  second_report?: Report
}

export interface DuplicateCandidateListResponse {
  items: DuplicateCandidate[]
  total: number
  limit: number
  offset: number
}

export interface DuplicateReviewRequest {
  decision: 'CONFIRMED_DUPLICATE' | 'NOT_DUPLICATE' | 'NEEDS_REVIEW'
  reason: string
  canonical_report_id?: string | null
}

export interface DuplicateReviewHistoryResponse {
  id: number
  candidate_id?: string | null
  duplicate_report_id: string
  canonical_report_id: string
  decision: string
  reason: string
  reviewer_id: string
  reviewed_at: string
}

export interface ScoringConfiguration {
  id: number
  version: string
  name: string
  description: string
  is_active: boolean
  weights: Record<string, number>
  created_at: string
}

export interface AreaScoreComponent {
  id: number
  category_id: number
  category: ReportCategory
  category_score?: number | null
  assigned_weight: number
  normalized_weight?: number | null
  weighted_contribution?: number | null
  report_count: number
  availability_state: 'OBSERVED' | 'INSUFFICIENT_DATA'
}

export interface AreaScore {
  id: string
  administrative_area_id: string
  configuration_id: number
  score?: number | null
  completeness_pct: number
  participating_categories_count: number
  total_categories_count: number
  eligible_reports_count: number
  calculation_timestamp: string
  is_current: boolean
  reason?: string | null
  components?: AreaScoreComponent[]
}

export interface AreaPriorityScore {
  id: string
  area_id: string
  area_name?: string | null
  area_code?: string | null
  area_type?: string | null
  configuration_id: number
  configuration_version?: string
  priority_score?: number | null
  priority_level: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INSUFFICIENT_DATA'
  sdi_score?: number | null
  confidence_score?: number | null
  completeness_pct?: number | null
  unresolved_reports_count: number
  latest_observation_at?: string | null
  last_inspected_at?: string | null
  never_inspected: boolean
  calculation_metadata: Record<string, unknown>
  is_current: boolean
  calculation_timestamp: string
}

export interface AreaPriorityListResponse {
  items: AreaPriorityScore[]
  total: number
  limit: number
  offset: number
}

export interface GeoJSONAreaFeature {
  type: 'Feature'
  id: string
  geometry: {
    type: 'MultiPolygon' | 'Polygon'
    coordinates: number[][][][] | number[][][]
  } | null
  properties: {
    id: string
    name: string
    code: string
    area_type: string
    parent_id?: string | null
    sdi_score?: number | null
    sdi_completeness_pct: number
    priority_score?: number | null
    priority_level: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INSUFFICIENT_DATA'
    confidence_score?: number | null
    confidence_completeness_pct: number
    unresolved_reports_count: number
  }
}

export interface GeoJSONAreaCollection {
  type: 'FeatureCollection'
  features: GeoJSONAreaFeature[]
}

export interface MaintenanceTaskEvent {
  id: number
  task_id: string
  from_status?: string | null
  to_status: string
  notes?: string | null
  created_at: string
  created_by_id: string
}

export interface MaintenanceTask {
  id: string
  report_id: string
  report?: Report
  title: string
  description?: string | null
  status: 'CREATED' | 'ASSIGNED' | 'ACCEPTED' | 'IN_PROGRESS' | 'BLOCKED' | 'COMPLETED' | 'CANCELLED'
  priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  assigned_to_id?: string | null
  assigned_to?: User | null
  created_by_id: string
  created_at: string
  updated_at?: string
  allow_duplicate: boolean
  duplicate_override_reason?: string | null
  events?: MaintenanceTaskEvent[]
}

export interface MaintenanceTaskListResponse {
  items: MaintenanceTask[]
  total: number
  limit: number
  offset: number
}

export interface TechnicianSummary {
  id: string
  email: string
  full_name: string
}

export interface NotificationItem {
  id: string
  user_id: string
  notification_type: string
  title: string
  message: string
  resource_type?: string | null
  resource_id?: string | null
  is_read: boolean
  created_at: string
}

export interface NotificationListResponse {
  items: NotificationItem[]
  total: number
  unread_count: number
  limit: number
  offset: number
}

// Analytics interfaces
export interface StatusCount {
  status: string
  count: number
}

export interface CategoryCount {
  category_id: number
  category_code: string
  category_name: string
  count: number
}

export interface AreaReportCount {
  area_id: string
  area_name: string
  area_code: string
  area_type: string
  count: number
}

export interface TimeSeriesPoint {
  date: string
  count: number
}

export interface ReportAnalyticsResponse {
  total_reports: number
  by_status: StatusCount[]
  by_category: CategoryCount[]
  by_area: AreaReportCount[]
  submitted_over_time: TimeSeriesPoint[]
  verified_count: number
  rejected_count: number
  duplicate_count: number
  pending_backlog_count: number
}

export interface SdiRangeDistribution {
  negligible: number
  low: number
  moderate: number
  high: number
  severe: number
  insufficient_data: number
}

export interface AreaSdiItem {
  area_id: string
  area_name: string
  area_code: string
  sdi_score?: number | null
  completeness_pct?: number | null
  calculation_timestamp?: string | null
}

export interface SdiAnalyticsResponse {
  total_areas_evaluated: number
  range_distribution: SdiRangeDistribution
  areas: AreaSdiItem[]
  insufficient_data_areas_count: number
}

export interface ConfidenceAnalyticsResponse {
  evaluated_areas_count: number
  average_area_confidence?: number | null
  average_completeness_pct?: number | null
  category_sample_counts: CategoryCount[]
  low_evidence_areas_count: number
}

export interface MaintenanceUserTaskCount {
  user_id: string
  user_name: string
  assigned_count: number
  completed_count: number
}

export interface MaintenanceAnalyticsResponse {
  total_tasks: number
  by_status: StatusCount[]
  by_priority: StatusCount[]
  average_completion_time_hours?: number | null
  overdue_tasks_count: number
  by_technician: MaintenanceUserTaskCount[]
}

export interface AnalyticsOverviewResponse {
  total_reports: number
  pending_verification: number
  verified_reports: number
  total_maintenance_tasks: number
  active_maintenance_tasks: number
  critical_priority_areas_count: number
  generated_at: string
}

export interface TrendsAnalyticsResponse {
  submissions_trend: TimeSeriesPoint[]
  verifications_trend: TimeSeriesPoint[]
  completions_trend: TimeSeriesPoint[]
}
