import React, { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  FileCheck2,
  CheckCircle2,
  XCircle,
  RotateCcw,
  Clock,
  MapPin,
  Camera,
  Shield,
  Layers,
  Search,
} from 'lucide-react'
import { moderationApi } from '../../api/moderation.api'
import { useUIStore } from '../../stores/ui.store'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Input } from '../../components/ui/Input'
import { Textarea } from '../../components/ui/Textarea'
import { Select } from '../../components/ui/Select'
import { Tabs } from '../../components/ui/Tabs'
import { Card, CardHeader, CardTitle, CardContent } from '../../components/ui/Card'
import { MapComponent } from '../../components/common/MapComponent'
import { formatDate, formatRelativeDays, formatCoordinates } from '../../lib/utils'
import type { Report } from '../../types'

export const ModerationQueuePage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'pending' | 'under_verification' | 'all'>('pending')
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  // Verification form state
  const [severity, setSeverity] = useState<number>(3)
  const [verificationNotes, setVerificationNotes] = useState('')
  const [rejectionReason, setRejectionReason] = useState('NOT_INFRASTRUCTURE_DEFICIENCY')
  const [rejectionNotes, setRejectionNotes] = useState('')
  const [isRejecting, setIsRejecting] = useState(false)
  const [reopenReason, setReopenReason] = useState('')
  const [isReopening, setIsReopening] = useState(false)

  const queryClient = useQueryClient()
  const { addToast } = useUIStore()

  // Queries
  const { data: pendingData, isLoading: isLoadingPending } = useQuery({
    queryKey: ['moderation-pending'],
    queryFn: () => moderationApi.getPendingQueue({ limit: 50 }),
  })

  const { data: underVerifData, isLoading: isLoadingUnderVerif } = useQuery({
    queryKey: ['moderation-under-verif'],
    queryFn: () => moderationApi.listReports({ status: 'UNDER_VERIFICATION', limit: 50 }),
  })

  const { data: allReportsData, isLoading: isLoadingAll } = useQuery({
    queryKey: ['moderation-all'],
    queryFn: () => moderationApi.listReports({ limit: 50 }),
    enabled: activeTab === 'all',
  })

  const reportsList =
    activeTab === 'pending'
      ? pendingData?.items || []
      : activeTab === 'under_verification'
      ? underVerifData?.items || []
      : allReportsData?.items || []

  const filteredReports = reportsList.filter((r) => {
    if (!searchQuery) return true
    const q = searchQuery.toLowerCase()
    return (
      r.title.toLowerCase().includes(q) ||
      r.category?.name.toLowerCase().includes(q) ||
      (r.address_text && r.address_text.toLowerCase().includes(q))
    )
  })

  // Set default selected report if none selected
  useEffect(() => {
    if (filteredReports.length > 0 && !selectedReportId) {
      setSelectedReportId(filteredReports[0].id)
    }
  }, [filteredReports, selectedReportId])

  const selectedReport =
    reportsList.find((r) => r.id === selectedReportId) || filteredReports[0] || null

  // Fetch full status history for selected report
  const { data: reportDetail } = useQuery({
    queryKey: ['report-detail', selectedReport?.id],
    queryFn: () => moderationApi.getReportDetail(selectedReport!.id),
    enabled: Boolean(selectedReport),
  })

  const activeReport = reportDetail || selectedReport

  // Mutations
  const startVerifMutation = useMutation({
    mutationFn: (reportId: string) => moderationApi.startVerification(reportId),
    onSuccess: (updatedReport) => {
      queryClient.invalidateQueries({ queryKey: ['moderation-pending'] })
      queryClient.invalidateQueries({ queryKey: ['moderation-under-verif'] })
      setSelectedReportId(updatedReport.id)
      addToast({
        type: 'info',
        title: 'Verification Locked',
        message: 'Report locked for moderation by your account.',
      })
    },
    onError: (err: any) => {
      addToast({
        type: 'error',
        title: 'Action Failed',
        message: err.response?.data?.detail || 'Could not start verification.',
      })
    },
  })

  const verifyMutation = useMutation({
    mutationFn: ({ id, sev, notes }: { id: string; sev: number; notes: string }) =>
      moderationApi.verifyReport(id, { severity: sev, notes }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['moderation-pending'] })
      queryClient.invalidateQueries({ queryKey: ['moderation-under-verif'] })
      queryClient.invalidateQueries({ queryKey: ['moderation-all'] })
      setVerificationNotes('')
      addToast({
        type: 'success',
        title: 'Report Verified',
        message: 'Deficiency verified and queued for SDI inclusion.',
      })
    },
    onError: (err: any) => {
      addToast({
        type: 'error',
        title: 'Verification Error',
        message: err.response?.data?.detail || 'Failed to verify report.',
      })
    },
  })

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason, notes }: { id: string; reason: string; notes: string }) =>
      moderationApi.rejectReport(id, { rejection_reason: reason, notes }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['moderation-pending'] })
      queryClient.invalidateQueries({ queryKey: ['moderation-under-verif'] })
      queryClient.invalidateQueries({ queryKey: ['moderation-all'] })
      setIsRejecting(false)
      setRejectionNotes('')
      addToast({
        type: 'info',
        title: 'Report Rejected',
        message: 'Report categorized as rejected with audit entry.',
      })
    },
    onError: (err: any) => {
      addToast({
        type: 'error',
        title: 'Rejection Error',
        message: err.response?.data?.detail || 'Failed to reject report.',
      })
    },
  })

  const reopenMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      moderationApi.reopenReport(id, { reason }),
    onSuccess: (updatedReport) => {
      queryClient.invalidateQueries({ queryKey: ['moderation-pending'] })
      queryClient.invalidateQueries({ queryKey: ['moderation-under-verif'] })
      queryClient.invalidateQueries({ queryKey: ['moderation-all'] })
      setIsReopening(false)
      setReopenReason('')
      setSelectedReportId(updatedReport.id)
      addToast({
        type: 'info',
        title: 'Report Reopened',
        message: 'Report status returned to UNDER_VERIFICATION.',
      })
    },
    onError: (err: any) => {
      addToast({
        type: 'error',
        title: 'Reopen Error',
        message: err.response?.data?.detail || 'Failed to reopen report.',
      })
    },
  })

  return (
    <div className="space-y-4">
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <FileCheck2 className="h-4 w-4 text-sky-500" />
            <h1 className="text-base font-semibold tracking-tight text-slate-900 dark:text-slate-100">
              Moderation &amp; Verification Workbench
            </h1>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Audit citizen observations, assign physical deficiency severity (1–5), and confirm SDI qualification.
          </p>
        </div>
      </div>

      {/* Tabs */}
      <Tabs
        activeTab={activeTab}
        onChange={(tab) => {
          setActiveTab(tab as any)
          setSelectedReportId(null)
        }}
        tabs={[
          { id: 'pending', label: 'FIFO Queue (Submitted)', count: pendingData?.total || 0 },
          { id: 'under_verification', label: 'Under Review', count: underVerifData?.total || 0 },
          { id: 'all', label: 'All Reports', count: allReportsData?.total },
        ]}
      />

      {/* Master-Detail Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Pane: Queue List */}
        <div className="lg:col-span-5 space-y-2.5 flex flex-col">
          {/* Search box */}
          <div className="relative">
            <Search className="h-3.5 w-3.5 absolute left-2.5 top-2.5 text-slate-400" />
            <Input
              placeholder="Filter by title, category, or street..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8"
            />
          </div>

          {/* Queue Items */}
          <div className="space-y-1.5 max-h-[700px] overflow-y-auto pr-0.5">
            {filteredReports.length > 0 ? (
              filteredReports.map((report) => {
                const isSelected = report.id === activeReport?.id
                return (
                  <div
                    key={report.id}
                    onClick={() => setSelectedReportId(report.id)}
                    className={`p-3 rounded-sm border text-xs cursor-pointer transition-all select-none ${
                      isSelected
                        ? 'border-[#244B3B] bg-[#DCE5D9]/30 dark:bg-[#18372C]/40 dark:border-[#829783]/80 shadow-2xs'
                        : 'border-[#829783]/25 bg-[#FFFEFA] dark:bg-[#1E211E] hover:border-[#829783]/50'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <span className="text-[10px] font-mono uppercase tracking-wider text-[#73766F] dark:text-[#829783] truncate">
                        {report.category?.name || 'General'}
                      </span>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <Badge variant="status" status={report.status} />
                        <span className="text-[10px] font-mono text-[#73766F]">
                          {formatRelativeDays(report.submitted_at)}
                        </span>
                      </div>
                    </div>

                    <div className="font-medium text-[#18372C] dark:text-[#F5F2EA] line-clamp-1">
                      {report.title}
                    </div>

                    {report.address_text && (
                      <div className="text-[11px] text-[#73766F] dark:text-[#829783] mt-1 truncate flex items-center gap-1">
                        <MapPin className="h-3 w-3 shrink-0 text-[#C36B48]" />
                        <span>{report.address_text}</span>
                      </div>
                    )}
                  </div>
                )
              })
            ) : (
              <div className="p-8 text-center text-xs text-slate-400 border border-dashed border-slate-200 dark:border-slate-800 rounded-md">
                No reports matching filter criteria.
              </div>
            )}
          </div>
        </div>

        {/* Right Pane: Report Inspector & Action Workbench */}
        <div className="lg:col-span-7">
          {activeReport ? (
            <Card className="p-4 space-y-4">
              {/* Header */}
              <div className="pb-3 border-b border-slate-100 dark:border-slate-800/80 flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-mono font-medium text-slate-400">
                      ID: {activeReport.id.slice(0, 8)}
                    </span>
                    <Badge variant="status" status={activeReport.status} />
                    <span className="text-[10px] font-mono text-slate-400">
                      {formatDate(activeReport.submitted_at, 'MMM d, yyyy HH:mm')}
                    </span>
                  </div>
                  <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                    {activeReport.title}
                  </h2>
                  <div className="text-xs text-slate-500 font-mono">
                    Category: {activeReport.category?.name} &bull; Jurisdiction: {activeReport.administrative_area?.name || 'Unassigned'}
                  </div>
                </div>

                <div className="text-right text-[11px] text-slate-400 font-mono shrink-0">
                  <div>Reporter: <span className="text-slate-600 dark:text-slate-300">ID #{activeReport.reporter_id?.slice(0, 8)}</span></div>
                  <div className="text-[10px] text-slate-500">{activeReport.observed_at ? formatDate(activeReport.observed_at, 'MMM d, yyyy') : ''}</div>
                </div>
              </div>

              {/* Description */}
              <div className="space-y-1">
                <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 block">
                  Observed Physical Condition
                </span>
                <p className="text-xs text-slate-700 dark:text-slate-300 bg-slate-50 dark:bg-slate-800/40 p-3 rounded-md border border-slate-200/60 dark:border-slate-700/60 leading-relaxed">
                  {activeReport.description}
                </p>
              </div>

              {/* Spatial Location & Coordinates Context */}
              <div className="space-y-1">
                <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-slate-400">
                  <span>Spatial Location (Privacy Fuzzed ~100m)</span>
                  <span>
                    {formatCoordinates(activeReport.latitude, activeReport.longitude)}
                  </span>
                </div>
                {activeReport.address_text && (
                  <div className="text-xs text-slate-600 dark:text-slate-400 pb-1">
                    Landmark: <span className="font-medium text-slate-800 dark:text-slate-200">{activeReport.address_text}</span>
                  </div>
                )}
                {activeReport.latitude && activeReport.longitude && (
                  <div className="h-44 w-full rounded-md overflow-hidden border border-slate-200 dark:border-slate-800 relative">
                    <MapComponent
                      markers={[
                        {
                          id: activeReport.id,
                          title: activeReport.title,
                          description: activeReport.description,
                          category_id: activeReport.category.id,
                          category_code: activeReport.category.code,
                          category_name: activeReport.category.name,
                          status: activeReport.status,
                          latitude: activeReport.latitude,
                          longitude: activeReport.longitude,
                          observed_at: activeReport.observed_at,
                          submitted_at: activeReport.submitted_at,
                          administrative_area_name: activeReport.administrative_area?.name,
                          has_media: Boolean(activeReport.media && activeReport.media.length > 0),
                        },
                      ]}
                      center={[activeReport.longitude, activeReport.latitude]}
                      zoom={14}
                      height="100%"
                    />
                  </div>
                )}
              </div>

              {/* Photo Evidence */}
              {activeReport.media && activeReport.media.length > 0 && (
                <div className="space-y-1">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 block">
                    Citizen Photo Evidence
                  </span>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    {activeReport.media.map((m) => {
                      const mediaUrl = m.download_url || `/api/v1/reports/${activeReport.id}/media/${m.id}`
                      return (
                        <div key={m.id} className="relative rounded-md overflow-hidden border border-slate-200 dark:border-slate-800 group">
                          <img
                            src={mediaUrl}
                            alt="Defect evidence"
                            className="h-28 w-full object-cover"
                          />
                          <div className="p-1 bg-slate-900/80 text-[10px] font-mono text-slate-300 truncate">
                            SHA: {m.checksum_sha256?.slice(0, 8)}...
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Action Station */}
              <div className="pt-3 border-t border-slate-100 dark:border-slate-800/80 space-y-3">
                <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400 block">
                  Moderation Determination
                </span>

                {activeReport.status === 'SUBMITTED' && (
                  <div className="flex items-center gap-3">
                    <Button
                      variant="primary"
                      className="w-full"
                      isLoading={startVerifMutation.isPending}
                      onClick={() => startVerifMutation.mutate(activeReport.id)}
                    >
                      <FileCheck2 className="h-4 w-4 mr-1.5" />
                      <span>Lock &amp; Start Verification</span>
                    </Button>
                  </div>
                )}

                {activeReport.status === 'UNDER_VERIFICATION' && (
                  <div className="space-y-3 bg-slate-50/70 dark:bg-slate-800/40 p-3 rounded-md border border-slate-200/80 dark:border-slate-700/80">
                    {/* Severity Selection 1–5 */}
                    <div className="space-y-1">
                      <div className="flex justify-between items-center text-xs">
                        <span className="font-medium text-[#18372C] dark:text-[#F5F2EA]">
                          Physical Deficiency Severity (1–5)
                        </span>
                        <span className="font-mono text-[#244B3B] dark:text-[#DCE5D9] font-semibold">
                          Grade {severity} of 5
                        </span>
                      </div>
                      <div className="grid grid-cols-5 gap-1.5 pt-1">
                        {[
                          { val: 1, label: 'Minor' },
                          { val: 2, label: 'Low' },
                          { val: 3, label: 'Moderate' },
                          { val: 4, label: 'High' },
                          { val: 5, label: 'Critical' },
                        ].map((s) => (
                          <button
                            key={s.val}
                            type="button"
                            onClick={() => setSeverity(s.val)}
                            className={`p-1.5 rounded-xs border text-center transition-all cursor-pointer ${
                              severity === s.val
                                ? 'border-[#244B3B] bg-[#244B3B] text-[#FFFEFA] dark:bg-[#DCE5D9] dark:text-[#18372C] font-bold shadow-2xs'
                                : 'border-[#829783]/30 bg-[#FFFEFA] dark:bg-[#1E211E] text-[#292D29] dark:text-[#F5F2EA] hover:bg-[#F5F2EA]'
                            }`}
                          >
                            <div className="font-mono text-xs">{s.val}</div>
                            <div className="text-[9px] truncate leading-tight opacity-90">{s.label}</div>
                          </button>
                        ))}
                      </div>
                    </div>

                    <Input
                      label="Verification Inspection Notes (Optional)"
                      placeholder="e.g. Confirmed broken light fixture with live exposed cables."
                      value={verificationNotes}
                      onChange={(e) => setVerificationNotes(e.target.value)}
                    />

                    {/* Actions */}
                    <div className="flex items-center gap-2 pt-1">
                      <Button
                        variant="primary"
                        className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white"
                        isLoading={verifyMutation.isPending}
                        onClick={() =>
                          verifyMutation.mutate({
                            id: activeReport.id,
                            sev: severity,
                            notes: verificationNotes,
                          })
                        }
                      >
                        <CheckCircle2 className="h-4 w-4 mr-1.5" />
                        <span>Approve &amp; Verify Defect</span>
                      </Button>

                      <Button
                        variant="outline"
                        className="text-rose-600 border-rose-300 dark:border-rose-900/60 hover:bg-rose-50 dark:hover:bg-rose-950/20"
                        onClick={() => setIsRejecting(!isRejecting)}
                      >
                        <XCircle className="h-4 w-4 mr-1" />
                        <span>Reject...</span>
                      </Button>
                    </div>

                    {isRejecting && (
                      <div className="pt-2 border-t border-slate-200 dark:border-slate-700 space-y-2">
                        <Select
                          label="Rejection Reason"
                          value={rejectionReason}
                          onChange={(e) => setRejectionReason(e.target.value)}
                        >
                          <option value="NOT_INFRASTRUCTURE_DEFICIENCY">Not an Infrastructure Deficiency</option>
                          <option value="INSUFFICIENT_EVIDENCE">Insufficient Evidence / Unclear</option>
                          <option value="DUPLICATE_REPORT">Duplicate of Existing Defect</option>
                          <option value="PRIVATE_PROPERTY">Located on Private Property</option>
                          <option value="SPAM_OR_OFFENSIVE">Spam or Non-Civic Content</option>
                        </Select>

                        <Input
                          label="Rejection Audit Justification"
                          placeholder="Provide audit rationale for citizen and supervisor review..."
                          value={rejectionNotes}
                          onChange={(e) => setRejectionNotes(e.target.value)}
                          required
                        />

                        <Button
                          variant="danger"
                          size="xs"
                          isLoading={rejectMutation.isPending}
                          disabled={!rejectionNotes.trim()}
                          onClick={() =>
                            rejectMutation.mutate({
                              id: activeReport.id,
                              reason: rejectionReason,
                              notes: rejectionNotes,
                            })
                          }
                        >
                          Confirm Rejection
                        </Button>
                      </div>
                    )}
                  </div>
                )}

                {(activeReport.status === 'VERIFIED' || activeReport.status === 'REJECTED') && (
                  <div className="flex items-center justify-between p-3 rounded-md bg-slate-50 dark:bg-slate-800/40 border border-slate-200/60 dark:border-slate-700/60">
                    <div className="text-xs space-y-0.5">
                      <div className="font-medium text-slate-800 dark:text-slate-200">
                        Determination Complete: {activeReport.status}
                      </div>
                      <div className="text-[11px] text-slate-500 font-mono">
                        Audited by staff on {formatDate(activeReport.updated_at)}
                      </div>
                    </div>

                    <Button
                      variant="outline"
                      size="xs"
                      onClick={() => setIsReopening(!isReopening)}
                    >
                      <RotateCcw className="h-3.5 w-3.5 mr-1" />
                      <span>Reopen...</span>
                    </Button>
                  </div>
                )}

                {isReopening && (
                  <div className="p-3 bg-amber-50/50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800/60 rounded-md space-y-2">
                    <Input
                      label="Reopen Audit Justification"
                      placeholder="e.g. Disputed by community inspector, requires re-verification."
                      value={reopenReason}
                      onChange={(e) => setReopenReason(e.target.value)}
                      required
                    />
                    <Button
                      variant="secondary"
                      size="xs"
                      isLoading={reopenMutation.isPending}
                      disabled={!reopenReason.trim()}
                      onClick={() =>
                        reopenMutation.mutate({
                          id: activeReport.id,
                          reason: reopenReason,
                        })
                      }
                    >
                      Return to Verification Queue
                    </Button>
                  </div>
                )}
              </div>
            </Card>
          ) : (
            <div className="p-12 text-center rounded-md border border-dashed border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
              <FileCheck2 className="h-8 w-8 text-slate-400 mx-auto mb-2" />
              <h3 className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                Select Report for Review
              </h3>
              <p className="text-[11px] text-slate-500 max-w-xs mx-auto mt-1">
                Choose an observation from the queue on the left to audit evidence, evaluate location context, and assign severity.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
