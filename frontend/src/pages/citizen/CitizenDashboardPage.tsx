import React from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { PlusCircle, FileText, CheckCircle2, Clock, MapPin, ArrowRight } from 'lucide-react'
import { reportsApi } from '../../api/reports.api'
import { useAuthStore } from '../../stores/auth.store'
import { StatCard } from '../../components/ui/StatCard'
import { Button } from '../../components/ui/Button'
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import { MapComponent } from '../../components/common/MapComponent'
import { formatDate } from '../../lib/utils'

export const CitizenDashboardPage: React.FC = () => {
  const { user } = useAuthStore()

  const { data: myReportsData, isLoading } = useQuery({
    queryKey: ['my-reports-dashboard'],
    queryFn: () => reportsApi.getMyReports({ limit: 5 }),
  })

  const { data: publicReports = [] } = useQuery({
    queryKey: ['public-map-reports-citizen-dashboard'],
    queryFn: () => reportsApi.getPublicMapReports({ limit: 100 }),
  })

  const reports = myReportsData?.items || []
  const totalReports = myReportsData?.total || 0
  const verifiedCount = reports.filter((r) => r.status === 'VERIFIED').length
  const underReviewCount = reports.filter(
    (r) => r.status === 'UNDER_VERIFICATION' || r.status === 'SUBMITTED'
  ).length

  return (
    <div className="space-y-4">
      {/* Welcoming Civic Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 sm:p-5 rounded-sm bg-[#FFFEFA] dark:bg-[#1E211E] border border-[#829783]/30 dark:border-[#829783]/20 shadow-2xs">
        <div className="space-y-0.5">
          <div className="flex items-center gap-2">
            <h1 className="font-serif-headline text-lg sm:text-xl font-normal tracking-tight text-[#18372C] dark:text-[#F5F2EA]">
              Welcome, {user?.full_name || 'Citizen'}
            </h1>
          </div>
          <p className="text-xs text-[#73766F] dark:text-[#829783]">
            Document public space infrastructure deficiencies to enable targeted municipal repairs.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/citizen/submit">
            <Button variant="primary" size="sm">
              <PlusCircle className="h-3.5 w-3.5 mr-1" />
              <span>Report Defect</span>
            </Button>
          </Link>
          <Link to="/map">
            <Button variant="outline" size="sm">
              <MapPin className="h-3.5 w-3.5 mr-1 text-[#C36B48]" />
              <span>Public Map</span>
            </Button>
          </Link>
        </div>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <StatCard
          title="Total Submissions"
          value={totalReports}
          icon={<FileText className="h-4 w-4" />}
          description="Reports submitted by your account"
        />
        <StatCard
          title="Defects Verified"
          value={verifiedCount}
          icon={<CheckCircle2 className="h-4 w-4 text-emerald-500" />}
          description="Approved by municipal verifiers"
        />
        <StatCard
          title="Under Verification"
          value={underReviewCount}
          icon={<Clock className="h-4 w-4 text-sky-500" />}
          description="Queued in moderation review"
        />
      </div>

      {/* Recent Submissions */}
      <Card>
        <CardHeader className="py-3 flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-xs uppercase tracking-wider text-slate-600 dark:text-slate-300">
              Your Recent Reports &amp; Status
            </CardTitle>
            <CardDescription>
              Track municipal verification and resolution progress on your logged defects.
            </CardDescription>
          </div>
          <Link
            to="/citizen/reports"
            className="text-xs text-[#244B3B] dark:text-[#DCE5D9] hover:underline font-medium inline-flex items-center gap-1 font-mono"
          >
            All Submissions <ArrowRight className="h-3 w-3" />
          </Link>
        </CardHeader>
        <CardContent className="p-0">
          {reports.length > 0 ? (
            <div className="divide-y divide-[#DCE5D9]/50 dark:divide-[#829783]/20">
              {reports.map((report) => (
                <div
                  key={report.id}
                  className="px-4 py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2 hover:bg-[#F5F2EA]/40 dark:hover:bg-[#18372C]/20 transition-colors"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-xs text-[#18372C] dark:text-[#F5F2EA]">
                        {report.title}
                      </span>
                      <Badge variant="status" status={report.status} />
                    </div>
                    <p className="text-[11px] text-[#73766F] dark:text-[#829783] font-mono">
                      {report.category?.name} &bull; {report.address_text || report.administrative_area?.name || 'Area Pending'} &bull; Observed {formatDate(report.observed_at, 'MMM d, yyyy')}
                    </p>
                  </div>
                  <Link to={`/citizen/reports/${report.id}`}>
                    <Button variant="outline" size="xs">
                      Inspect Status
                    </Button>
                  </Link>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-xs text-[#73766F] dark:text-[#829783]">
              You haven't submitted any infrastructure deficiency reports yet.
              <div className="mt-2.5">
                <Link to="/citizen/submit">
                  <Button size="xs" variant="primary">Submit Your First Report</Button>
                </Link>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Interactive Public Deficiency Map */}
      <Card>
        <CardHeader className="py-3 flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-xs uppercase tracking-wider text-[#73766F] dark:text-[#829783]">
              Civic Infrastructure Deficiency Map
            </CardTitle>
            <CardDescription>
              Community defect observations with privacy-fuzzed street coordinates (~100m).
            </CardDescription>
          </div>
          <Link
            to="/map"
            className="text-xs text-[#244B3B] dark:text-[#DCE5D9] hover:underline font-medium inline-flex items-center gap-1 font-mono"
          >
            Explore Full Map <ArrowRight className="h-3 w-3" />
          </Link>
        </CardHeader>
        <CardContent className="p-0">
          <div className="h-72 w-full relative">
            <MapComponent
              markers={publicReports}
              height="100%"
            />
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
