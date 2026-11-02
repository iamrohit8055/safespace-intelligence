import React from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Clock, MapPin, ShieldCheck, CheckCircle2, Image as ImageIcon, AlertTriangle } from 'lucide-react'
import { reportsApi } from '../../api/reports.api'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Card, CardHeader, CardTitle, CardContent } from '../../components/ui/Card'
import { MapComponent } from '../../components/common/MapComponent'
import { formatDate } from '../../lib/utils'

export const CitizenReportDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()

  const { data: report, isLoading, error } = useQuery({
    queryKey: ['report-detail', id],
    queryFn: () => reportsApi.getReport(id!),
    enabled: Boolean(id),
  })

  if (isLoading) {
    return (
      <div className="p-8 text-center text-xs text-slate-500 animate-pulse">
        Loading deficiency report details...
      </div>
    )
  }

  if (error || !report) {
    return (
      <div className="p-8 text-center space-y-4">
        <p className="text-sm text-rose-500 font-semibold">Report not found or unavailable.</p>
        <Link to="/citizen/reports">
          <Button variant="outline" size="sm">
            <ArrowLeft className="h-4 w-4 mr-1" /> Back to My Reports
          </Button>
        </Link>
      </div>
    )
  }

  const steps = ['SUBMITTED', 'UNDER_VERIFICATION', 'VERIFIED']
  const currentStepIdx =
    report.status === 'REJECTED' ? -1 : steps.indexOf(report.status)

  return (
    <div className="space-y-4 max-w-4xl mx-auto">
      <div className="flex items-center justify-between pb-2 border-b border-slate-200 dark:border-slate-800">
        <Link to="/citizen/reports">
          <Button variant="outline" size="xs">
            <ArrowLeft className="h-3 w-3 mr-1" /> Back to Submissions
          </Button>
        </Link>
        <Badge variant="status" status={report.status} />
      </div>

      {/* Title & Metadata Header */}
      <div className="p-4 rounded-md bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-2">
        <div className="flex items-start justify-between gap-4">
          <div>
            <span className="text-[11px] font-mono font-medium text-sky-600 dark:text-sky-400 uppercase tracking-wider">
              {report.category.name} ({report.category.code})
            </span>
            <h1 className="text-base font-semibold text-slate-900 dark:text-slate-100 mt-0.5">
              {report.title}
            </h1>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-4 text-[11px] font-mono text-slate-500 pt-2 border-t border-slate-100 dark:border-slate-800">
          <span className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            Observed: {formatDate(report.observed_at, 'MMM d, yyyy HH:mm')}
          </span>
          <span className="flex items-center gap-1">
            <MapPin className="h-3 w-3" />
            {report.administrative_area?.name || 'Area unassigned'} ({report.administrative_area?.code || 'N/A'})
          </span>
        </div>
      </div>

      {/* Lifecycle Status Stepper */}
      <div className="p-4 rounded-md bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
        <h3 className="text-[11px] font-mono font-medium uppercase tracking-wider text-slate-500 mb-3">
          Defect Resolution Lifecycle
        </h3>
        {report.status === 'REJECTED' ? (
          <div className="p-3 rounded-md bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-700 dark:text-rose-300 text-xs flex items-start gap-2.5">
            <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Report Rejected During Moderation</p>
              <p className="mt-1">
                Reason: {report.rejection_reason || 'Does not describe a valid physical deficiency.'}
              </p>
              {report.verification_notes && (
                <p className="mt-1 text-slate-500">Notes: {report.verification_notes}</p>
              )}
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-2 text-center text-xs">
            <div
              className={`p-3 rounded-2xl border ${
                currentStepIdx >= 0
                  ? 'border-indigo-500 bg-indigo-50/50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 font-bold'
                  : 'border-slate-200 text-slate-400'
              }`}
            >
              1. Submitted
            </div>
            <div
              className={`p-3 rounded-2xl border ${
                currentStepIdx >= 1
                  ? 'border-indigo-500 bg-indigo-50/50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 font-bold'
                  : 'border-slate-200 text-slate-400'
              }`}
            >
              2. Under Verification
            </div>
            <div
              className={`p-3 rounded-2xl border ${
                currentStepIdx >= 2
                  ? 'border-emerald-500 bg-emerald-50/50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 font-bold'
                  : 'border-slate-200 text-slate-400'
              }`}
            >
              3. Verified Defect
            </div>
          </div>
        )}

        {report.status === 'VERIFIED' && report.verified_severity && (
          <div className="mt-4 p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 text-xs text-emerald-800 dark:text-emerald-300 flex items-center justify-between">
            <span className="font-medium">Physical Deficiency Severity Scale:</span>
            <span className="font-bold text-sm">{report.verified_severity} / 5</span>
          </div>
        )}
      </div>

      {/* Description & Location */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Physical Observation</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed whitespace-pre-wrap">
              {report.description}
            </p>

            {report.address_text && (
              <div className="pt-3 border-t border-slate-100 dark:border-slate-800 text-xs">
                <span className="text-slate-400 block text-[10px]">Landmark</span>
                <span className="text-slate-700 dark:text-slate-200 font-medium">
                  {report.address_text}
                </span>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Photographic Evidence Gallery */}
        <Card>
          <CardHeader>
            <CardTitle>Photographic Evidence</CardTitle>
          </CardHeader>
          <CardContent>
            {report.media && report.media.length > 0 ? (
              <div className="space-y-3">
                {report.media.map((media) => {
                  const mediaUrl =
                    media.download_url ||
                    `/api/v1/reports/${report.id}/media/${media.id}`
                  return (
                    <div
                      key={media.id}
                      className="rounded-2xl overflow-hidden border border-slate-200 dark:border-slate-800 bg-slate-100 dark:bg-slate-900"
                    >
                      <img
                        src={mediaUrl}
                        alt="Infrastructure evidence"
                        className="w-full h-48 object-cover"
                      />
                      <div className="p-2.5 text-[10px] text-slate-500 flex items-center justify-between">
                        <span>SHA-256: {media.checksum_sha256.substring(0, 12)}...</span>
                        <span>{(media.file_size_bytes / (1024 * 1024)).toFixed(2)} MB</span>
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="p-8 text-center text-xs text-slate-400 border border-dashed border-slate-200 dark:border-slate-800 rounded-2xl">
                <ImageIcon className="h-8 w-8 mx-auto mb-2 opacity-50" />
                No photo evidence uploaded for this report.
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Map Location Preview */}
      <Card>
        <CardHeader>
          <CardTitle>Spatial Location</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-64 rounded-2xl overflow-hidden">
            <MapComponent
              center={[report.longitude, report.latitude]}
              zoom={14}
              selectedCoordinates={{
                latitude: report.latitude,
                longitude: report.longitude,
              }}
              height="100%"
            />
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-slate-500 font-mono">
            <span>Lat: {report.latitude.toFixed(6)}</span>
            <span>Lng: {report.longitude.toFixed(6)}</span>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
