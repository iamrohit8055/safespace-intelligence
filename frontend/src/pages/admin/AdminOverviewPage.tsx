import React from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  FileCheck2,
  AlertTriangle,
  Wrench,
  Layers,
  MapPin,
  ArrowRight,
  ListOrdered,
  Clock,
  Shield,
  Activity,
} from 'lucide-react'
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from 'recharts'
import { analyticsApi } from '../../api/analytics.api'
import { reportsApi } from '../../api/reports.api'
import { intelligenceApi } from '../../api/intelligence.api'
import { priorityApi } from '../../api/priority.api'
import { MapComponent } from '../../components/common/MapComponent'
import { StatCard } from '../../components/ui/StatCard'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../../components/ui/Card'
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '../../components/ui/Table'
import { formatScore, formatDate } from '../../lib/utils'

export const AdminOverviewPage: React.FC = () => {
  const { data: overview, isLoading: isLoadingOverview } = useQuery({
    queryKey: ['analytics-overview'],
    queryFn: analyticsApi.getOverview,
    refetchInterval: 30000,
  })

  const { data: trends } = useQuery({
    queryKey: ['analytics-trends'],
    queryFn: () => analyticsApi.getTrendsAnalytics(),
  })

  const { data: topPriorities } = useQuery({
    queryKey: ['top-priorities-overview'],
    queryFn: () => priorityApi.listAreaPriorities({ limit: 5, sort_by: 'score_desc' }),
  })

  const { data: publicReports = [] } = useQuery({
    queryKey: ['public-map-reports-admin-overview'],
    queryFn: () => reportsApi.getPublicMapReports({ limit: 60 }),
  })

  const { data: geoJsonData } = useQuery({
    queryKey: ['areas-geojson-admin-overview'],
    queryFn: intelligenceApi.getAreasGeoJSON,
  })

  // Format trends data for Recharts
  const chartData = (trends?.submissions_trend || []).map((sub, i) => {
    const verif = trends?.verifications_trend?.[i]
    const comp = trends?.completions_trend?.[i]
    return {
      date: sub.date.slice(5), // MM-DD
      submissions: sub.count,
      verifications: verif ? verif.count : 0,
      repairs: comp ? comp.count : 0,
    }
  })

  return (
    <div className="space-y-5">
      {/* Page Title & Operational Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#829783]/25 dark:border-[#829783]/20">
        <div>
          <span className="text-[10px] font-mono uppercase tracking-widest text-[#C36B48] font-semibold block">
            Command &amp; Surveillance
          </span>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="h-2 w-2 rounded-full bg-[#244B3B] dark:bg-[#DCE5D9] animate-pulse" />
            <h1 className="font-serif-headline text-xl sm:text-2xl font-normal tracking-tight text-[#18372C] dark:text-[#F5F2EA]">
              Intelligence Operations Center
            </h1>
          </div>
          <p className="text-xs text-[#73766F] dark:text-[#829783] mt-0.5">
            Real-time municipal surveillance, verification backlog, and spatial inspection prioritization.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/admin/map">
            <Button variant="outline" size="sm">
              <MapPin className="h-3.5 w-3.5 text-[#C36B48]" />
              <span>Full Spatial Map</span>
            </Button>
          </Link>
          <Link to="/admin/priorities">
            <Button variant="primary" size="sm">
              <ListOrdered className="h-3.5 w-3.5" />
              <span>Ranked Priorities</span>
            </Button>
          </Link>
        </div>
      </div>

      {/* Primary Operational Metric Tiles */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard
          title="Citizen Submissions"
          value={overview?.total_reports ?? 0}
          icon={<Layers className="h-4 w-4" />}
          description="Total physical defect logs"
        />
        <StatCard
          title="Moderation Backlog"
          value={overview?.pending_verification ?? 0}
          icon={<FileCheck2 className="h-4 w-4 text-amber-500" />}
          description="Awaiting staff inspection"
          badge={
            (overview?.pending_verification ?? 0) > 0 ? (
              <Badge variant="status" status="UNDER_VERIFICATION">
                Action Required
              </Badge>
            ) : undefined
          }
        />
        <StatCard
          title="Verified Deficiencies"
          value={overview?.verified_reports ?? 0}
          icon={<Shield className="h-4 w-4 text-emerald-500" />}
          description="Qualified for SDI scoring"
        />
        <StatCard
          title="Critical Inspection Wards"
          value={overview?.critical_priority_areas_count ?? 0}
          icon={<AlertTriangle className="h-4 w-4 text-rose-500" />}
          description="Immediate field dispatch tier"
        />
      </div>

      {/* Main Operational Split: Priority Table & Spatial Preview */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left: Ranked High-Priority Areas Requiring Field Inspection */}
        <div className="lg:col-span-7 space-y-5">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between py-3">
              <div>
                <CardTitle className="text-xs uppercase tracking-wider text-slate-600 dark:text-slate-300">
                  Priority Inspection Queue
                </CardTitle>
                <CardDescription>
                  Municipal wards ranked by multi-factor deficiency score and inspection urgency.
                </CardDescription>
              </div>
              <Link
                to="/admin/priorities"
                className="text-xs text-sky-600 dark:text-sky-400 hover:underline inline-flex items-center gap-1 font-medium"
              >
                View All <ArrowRight className="h-3 w-3" />
              </Link>
            </CardHeader>
            <CardContent className="p-0">
              {topPriorities?.items && topPriorities.items.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Ward / Administrative Area</TableHead>
                      <TableHead>Priority Tier</TableHead>
                      <TableHead className="text-right">Priority Score</TableHead>
                      <TableHead className="text-right">SDI Index</TableHead>
                      <TableHead className="text-right">Unresolved</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {topPriorities.items.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell>
                          <Link
                            to={`/admin/areas/${item.area_id}`}
                            className="font-medium text-slate-900 dark:text-slate-100 hover:text-sky-600 dark:hover:text-sky-400 block"
                          >
                            {item.area_name}
                          </Link>
                          <span className="text-[10px] font-mono text-slate-400">
                            {item.area_code}
                          </span>
                        </TableCell>
                        <TableCell>
                          <Badge variant="priority" priority={item.priority_level}>
                            {item.priority_level}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right font-mono-numbers font-medium text-slate-900 dark:text-slate-100">
                          {formatScore(item.priority_score)}
                        </TableCell>
                        <TableCell className="text-right font-mono-numbers text-slate-600 dark:text-slate-300">
                          {formatScore(item.sdi_score)}
                        </TableCell>
                        <TableCell className="text-right font-mono-numbers text-slate-600 dark:text-slate-400">
                          {item.unresolved_reports_count}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <div className="p-6 text-center text-xs text-slate-400">
                  No priority rankings computed yet.
                </div>
              )}
            </CardContent>
          </Card>

          {/* Activity Telemetry Chart */}
          <Card>
            <CardHeader className="py-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-xs uppercase tracking-wider text-slate-600 dark:text-slate-300">
                    Deficiency Throughput &amp; Resolution Velocity
                  </CardTitle>
                  <CardDescription>
                    Daily trends comparing citizen submissions, completed verifications, and technician repairs.
                  </CardDescription>
                </div>
                <Activity className="h-4 w-4 text-slate-400" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="h-56 w-full pt-1">
                {chartData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
                      <defs>
                        <linearGradient id="colorSub" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#244B3B" stopOpacity={0.4} />
                          <stop offset="95%" stopColor="#244B3B" stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="colorVerif" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#C5A66B" stopOpacity={0.4} />
                          <stop offset="95%" stopColor="#C5A66B" stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="colorRep" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#C36B48" stopOpacity={0.4} />
                          <stop offset="95%" stopColor="#C36B48" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="2 2" stroke="#829783" opacity={0.2} vertical={false} />
                      <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#73766F' }} stroke="#829783" opacity={0.3} />
                      <YAxis tick={{ fontSize: 10, fill: '#73766F' }} stroke="#829783" opacity={0.3} allowDecimals={false} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#1E211E',
                          borderColor: '#829783',
                          borderRadius: '2px',
                          fontSize: '11px',
                          color: '#F5F2EA',
                          boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.2)',
                        }}
                      />
                      <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '6px' }} />
                      <Area
                        type="monotone"
                        dataKey="submissions"
                        stroke="#244B3B"
                        strokeWidth={1.5}
                        fillOpacity={1}
                        fill="url(#colorSub)"
                        name="Submissions"
                      />
                      <Area
                        type="monotone"
                        dataKey="verifications"
                        stroke="#C5A66B"
                        strokeWidth={1.5}
                        fillOpacity={1}
                        fill="url(#colorVerif)"
                        name="Verifications"
                      />
                      <Area
                        type="monotone"
                        dataKey="repairs"
                        stroke="#C36B48"
                        strokeWidth={1.5}
                        fillOpacity={1}
                        fill="url(#colorRep)"
                        name="Repairs"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-xs text-slate-400">
                    Aggregating throughput telemetry...
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right: Live Spatial Surveillance Canvas */}
        <div className="lg:col-span-5 space-y-5">
          <Card className="flex flex-col h-full">
            <CardHeader className="flex flex-row items-center justify-between py-3">
              <div>
                <CardTitle className="text-xs uppercase tracking-wider text-slate-600 dark:text-slate-300">
                  Spatial Deficiency Surveillance
                </CardTitle>
                <CardDescription>
                  Geographic distribution with administrative boundaries.
                </CardDescription>
              </div>
              <Link
                to="/admin/map"
                className="text-xs text-sky-600 dark:text-sky-400 hover:underline font-medium inline-flex items-center gap-1"
              >
                Expand <ArrowRight className="h-3 w-3" />
              </Link>
            </CardHeader>
            <CardContent className="p-0 flex-1 min-h-[360px]">
              <div className="h-full w-full min-h-[360px] relative">
                <MapComponent
                  markers={publicReports}
                  geoJsonAreas={geoJsonData}
                  height="100%"
                />
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
