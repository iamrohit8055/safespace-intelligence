import React from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Layers, Eye, AlertTriangle } from 'lucide-react'
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts'
import { analyticsApi } from '../../api/analytics.api'
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '../../components/ui/Card'
import { StatCard } from '../../components/ui/StatCard'
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { formatScore, formatDate, formatPercentage } from '../../lib/utils'

export const SDIAnalyticsPage: React.FC = () => {
  const { data: sdiData, isLoading } = useQuery({
    queryKey: ['analytics-sdi'],
    queryFn: () => analyticsApi.getSdiAnalytics(),
  })

  const dist = sdiData?.range_distribution
  const chartData = [
    { tier: 'Negligible (0–1)', count: dist?.negligible ?? 0, fill: '#10b981' },
    { tier: 'Low (1–2)', count: dist?.low ?? 0, fill: '#0284c7' },
    { tier: 'Moderate (2–3)', count: dist?.moderate ?? 0, fill: '#eab308' },
    { tier: 'High (3–4)', count: dist?.high ?? 0, fill: '#f97316' },
    { tier: 'Severe (4–5)', count: dist?.severe ?? 0, fill: '#ef4444' },
    { tier: 'No Data', count: dist?.insufficient_data ?? 0, fill: '#64748b' },
  ]

  const areas = sdiData?.areas || []

  return (
    <div className="space-y-4">
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <Layers className="h-4 w-4 text-sky-500" />
            <h1 className="text-base font-semibold tracking-tight text-slate-900 dark:text-slate-100">
              Safety Deficiency Index (SDI) Analytics
            </h1>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Cross-jurisdictional deficiency distribution, severity clustering, and data completeness metrics.
          </p>
        </div>
      </div>

      {/* KPI Tiles */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <StatCard
          title="Administrative Areas Evaluated"
          value={sdiData?.total_areas_evaluated ?? 0}
          icon={<Layers className="h-4 w-4" />}
          description="Bounded municipal polygons"
        />
        <StatCard
          title="Severe / High Deficiency Areas"
          value={(dist?.severe ?? 0) + (dist?.high ?? 0)}
          icon={<AlertTriangle className="h-4 w-4 text-rose-500" />}
          description="Wards with SDI score > 3.0"
        />
        <StatCard
          title="Insufficient Data Areas"
          value={sdiData?.insufficient_data_areas_count ?? 0}
          icon={<Layers className="h-4 w-4 text-slate-400" />}
          description="Awaiting verified baseline defects"
        />
      </div>

      {/* Distribution Chart */}
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-xs uppercase tracking-wider text-slate-600 dark:text-slate-300">
            SDI Severity Tier Distribution
          </CardTitle>
          <CardDescription>
            Number of administrative wards grouped by physical infrastructure deficiency brackets.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-56 w-full pt-1">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
                <CartesianGrid strokeDasharray="2 2" stroke="#334155" opacity={0.2} vertical={false} />
                <XAxis dataKey="tier" tick={{ fontSize: 10, fill: '#64748b' }} stroke="#cbd5e1" opacity={0.3} />
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
                <Bar dataKey="count" fill="#0284c7" radius={[2, 2, 0, 0]} name="Wards" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Area SDI Table */}
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-xs uppercase tracking-wider text-slate-600 dark:text-slate-300">
            Administrative Area SDI Scores
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Ward Area</TableHead>
                <TableHead>Code</TableHead>
                <TableHead className="text-right">SDI Deficiency Score</TableHead>
                <TableHead className="text-right">Data Completeness</TableHead>
                <TableHead>Calculation Timestamp</TableHead>
                <TableHead className="text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {areas.length > 0 ? (
                areas.map((a) => (
                  <TableRow key={a.area_id}>
                    <TableCell className="font-medium text-slate-900 dark:text-slate-100">
                      {a.area_name}
                    </TableCell>
                    <TableCell className="font-mono text-[10px] text-slate-400">
                      {a.area_code}
                    </TableCell>
                    <TableCell className="text-right font-mono-numbers font-semibold text-sky-600 dark:text-sky-400">
                      {formatScore(a.sdi_score)}
                    </TableCell>
                    <TableCell className="text-right font-mono-numbers text-slate-700 dark:text-slate-300">
                      {formatPercentage(a.completeness_pct)}
                    </TableCell>
                    <TableCell className="font-mono text-[10px] text-slate-400">
                      {formatDate(a.calculation_timestamp, 'MMM d, yyyy HH:mm')}
                    </TableCell>
                    <TableCell className="text-right">
                      <Link to={`/admin/areas/${a.area_id}`}>
                        <Button variant="outline" size="xs">
                          <Eye className="h-3 w-3 mr-1" /> Inspect
                        </Button>
                      </Link>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-slate-400">
                    No area SDI records available.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
