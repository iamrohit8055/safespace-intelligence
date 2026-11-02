import React from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart3,
  CheckCircle2,
  Clock,
  CopyCheck,
  Wrench,
  Activity,
} from 'lucide-react'
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts'
import { analyticsApi } from '../../api/analytics.api'
import { StatCard } from '../../components/ui/StatCard'
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '../../components/ui/Card'
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '../../components/ui/Table'
import { Badge } from '../../components/ui/Badge'
import { formatScore } from '../../lib/utils'

export const SystemAnalyticsPage: React.FC = () => {
  const { data: reportAnalytics } = useQuery({
    queryKey: ['analytics-reports'],
    queryFn: () => analyticsApi.getReportsAnalytics(),
  })

  const { data: maintenanceAnalytics } = useQuery({
    queryKey: ['analytics-maintenance'],
    queryFn: () => analyticsApi.getMaintenanceAnalytics(),
  })

  const categoryData = (reportAnalytics?.by_category || []).map((c) => ({
    category: c.category_name,
    count: c.count,
  }))

  const technicians = maintenanceAnalytics?.by_technician || []

  return (
    <div className="space-y-4">
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-sky-500" />
            <h1 className="text-base font-semibold tracking-tight text-slate-900 dark:text-slate-100">
              System Infrastructure &amp; Operational Analytics
            </h1>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            End-to-end metrics on citizen report volume, verification throughput, and field maintenance completion.
          </p>
        </div>
      </div>

      {/* Reports KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard
          title="Total Reports Received"
          value={reportAnalytics?.total_reports ?? 0}
          icon={<BarChart3 className="h-4 w-4" />}
          description="Cumulative citizen submissions"
        />
        <StatCard
          title="Defect Verification Rate"
          value={
            reportAnalytics?.total_reports
              ? `${Math.round(((reportAnalytics.verified_count || 0) / reportAnalytics.total_reports) * 100)}%`
              : '0%'
          }
          icon={<CheckCircle2 className="h-4 w-4 text-emerald-500" />}
          description={`${reportAnalytics?.verified_count ?? 0} confirmed deficiencies`}
        />
        <StatCard
          title="Pending Moderation Queue"
          value={reportAnalytics?.pending_backlog_count ?? 0}
          icon={<Clock className="h-4 w-4 text-amber-500" />}
          description="Awaiting staff review"
        />
        <StatCard
          title="Deduplicated Reports"
          value={reportAnalytics?.duplicate_count ?? 0}
          icon={<CopyCheck className="h-4 w-4 text-sky-500" />}
          description="Proximity duplicate links"
        />
      </div>

      {/* Grid: Category Breakdown & Technician Output */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Category Defect Volume */}
        <div className="lg:col-span-7">
          <Card className="h-full flex flex-col">
            <CardHeader className="py-3">
              <CardTitle className="text-xs uppercase tracking-wider text-slate-600 dark:text-slate-300">
                Defect Volume by Category Taxonomy
              </CardTitle>
              <CardDescription>
                Citizen observation volume across physical infrastructure categories.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex-1">
              <div className="h-56 w-full pt-1">
                {categoryData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={categoryData} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="2 2" stroke="#334155" opacity={0.2} vertical={false} />
                      <XAxis dataKey="category" tick={{ fontSize: 10, fill: '#64748b' }} stroke="#cbd5e1" opacity={0.3} />
                      <YAxis tick={{ fontSize: 10, fill: '#64748b' }} stroke="#cbd5e1" opacity={0.3} allowDecimals={false} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#0f172a',
                          borderColor: '#1e293b',
                          borderRadius: '4px',
                          fontSize: '11px',
                          color: '#f8fafc',
                        }}
                      />
                      <Bar dataKey="count" fill="#0284c7" radius={[2, 2, 0, 0]} name="Reports" />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-xs text-slate-400">
                    No category breakdown data.
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Technician Workload Table */}
        <div className="lg:col-span-5">
          <Card className="h-full flex flex-col">
            <CardHeader className="py-3">
              <CardTitle className="text-xs uppercase tracking-wider text-slate-600 dark:text-slate-300">
                Field Technician Workload
              </CardTitle>
              <CardDescription>
                Active assignments and completion metrics per field technician.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0 flex-1">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Field Technician</TableHead>
                    <TableHead className="text-right">Assigned</TableHead>
                    <TableHead className="text-right">Completed</TableHead>
                    <TableHead className="text-right">Velocity</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {technicians.length > 0 ? (
                    technicians.map((t) => {
                      const total = (t.assigned_count || 0) + (t.completed_count || 0)
                      const rate = total > 0 ? Math.round(((t.completed_count || 0) / total) * 100) : 0
                      return (
                        <TableRow key={t.user_id}>
                          <TableCell className="font-medium text-slate-900 dark:text-slate-100">
                            {t.user_name}
                          </TableCell>
                          <TableCell className="text-right font-mono-numbers text-slate-600 dark:text-slate-400">
                            {t.assigned_count}
                          </TableCell>
                          <TableCell className="text-right font-mono-numbers font-medium text-emerald-600 dark:text-emerald-400">
                            {t.completed_count}
                          </TableCell>
                          <TableCell className="text-right font-mono-numbers text-xs text-slate-600 dark:text-slate-300">
                            {rate}%
                          </TableCell>
                        </TableRow>
                      )
                    })
                  ) : (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center py-6 text-slate-400">
                        No technician assignment data available.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
