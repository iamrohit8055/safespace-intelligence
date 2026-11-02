import React from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  RefreshCw,
  Layers,
  ListOrdered,
  Activity,
  CheckCircle2,
  Clock,
  AlertTriangle,
  History,
} from 'lucide-react'
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts'
import { intelligenceApi } from '../../api/intelligence.api'
import { priorityApi } from '../../api/priority.api'
import { useUIStore } from '../../stores/ui.store'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Card, CardHeader, CardTitle, CardContent } from '../../components/ui/Card'
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '../../components/ui/Table'
import { formatScore, formatDate } from '../../lib/utils'

export const AreaDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const { addToast } = useUIStore()

  // Queries
  const { data: sdiScore, isLoading: isLoadingSdi } = useQuery({
    queryKey: ['area-sdi', id],
    queryFn: () => intelligenceApi.getAreaSDI(id!),
    enabled: Boolean(id),
  })

  const { data: sdiHistory = [] } = useQuery({
    queryKey: ['area-sdi-history', id],
    queryFn: () => intelligenceApi.getAreaSDIHistory(id!, { limit: 10 }),
    enabled: Boolean(id),
  })

  const { data: priorityScore, isLoading: isLoadingPriority } = useQuery({
    queryKey: ['area-priority', id],
    queryFn: () => priorityApi.getAreaPriority(id!),
    enabled: Boolean(id),
  })

  const { data: priorityHistory = [] } = useQuery({
    queryKey: ['area-priority-history', id],
    queryFn: () => priorityApi.getAreaPriorityHistory(id!, { limit: 10 }),
    enabled: Boolean(id),
  })

  // Mutations
  const recalcSdi = useMutation({
    mutationFn: () => intelligenceApi.calculateAreaSDI(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['area-sdi', id] })
      queryClient.invalidateQueries({ queryKey: ['area-sdi-history', id] })
      addToast({
        type: 'success',
        title: 'SDI Recalculated',
        message: 'Deficiency scores updated successfully.',
      })
    },
  })

  const recalcPriority = useMutation({
    mutationFn: () => priorityApi.calculateAreaPriority(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['area-priority', id] })
      queryClient.invalidateQueries({ queryKey: ['area-priority-history', id] })
      addToast({
        type: 'success',
        title: 'Priority Recalculated',
        message: 'Inspection priority updated successfully.',
      })
    },
  })

  if (isLoadingSdi || isLoadingPriority) {
    return (
      <div className="p-12 text-center text-xs text-slate-500 animate-pulse">
        Loading administrative area intelligence data...
      </div>
    )
  }

  // Format SDI history for chart
  const historyChartData = [...sdiHistory].reverse().map((h, i) => ({
    timestamp: formatDate(h.calculation_timestamp, 'MM/dd HH:mm'),
    score: h.score ? Number(h.score.toFixed(2)) : null,
    completeness: Number(h.completeness_pct.toFixed(1)),
  }))

  return (
    <div className="space-y-4">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-200 dark:border-slate-800">
        <div className="flex items-center gap-2.5">
          <Link to="/admin/map">
            <Button variant="outline" size="xs">
              <ArrowLeft className="h-3.5 w-3.5 mr-1" /> Back
            </Button>
          </Link>
          <div>
            <h1 className="text-base font-semibold tracking-tight text-slate-900 dark:text-slate-100">
              {priorityScore?.area_name || 'Administrative Area Details'}
            </h1>
            <p className="text-xs text-slate-500 font-mono">
              Code: {priorityScore?.area_code} &bull; Type: {priorityScore?.area_type?.toUpperCase()}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {priorityScore?.priority_level && (
            <Badge variant="priority" priority={priorityScore.priority_level} />
          )}
          <Button
            variant="outline"
            size="xs"
            isLoading={recalcSdi.isPending}
            onClick={() => recalcSdi.mutate()}
          >
            <RefreshCw className="h-3 w-3 mr-1" /> Recalc SDI
          </Button>
          <Button
            variant="primary"
            size="xs"
            isLoading={recalcPriority.isPending}
            onClick={() => recalcPriority.mutate()}
          >
            Recalc Priority
          </Button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Card className="p-3">
          <span className="text-[10px] font-mono font-medium uppercase tracking-wider text-slate-400">
            Active SDI Score
          </span>
          <div className="text-2xl font-bold font-mono-numbers text-sky-600 dark:text-sky-400 mt-1">
            {formatScore(sdiScore?.score)}
          </div>
          <p className="text-[10px] text-slate-500 mt-1">Scale: 0.00 – 100.00</p>
        </Card>

        <Card className="p-3">
          <span className="text-[10px] font-mono font-medium uppercase tracking-wider text-slate-400">
            Data Completeness
          </span>
          <div className="text-2xl font-bold font-mono-numbers text-slate-800 dark:text-slate-200 mt-1">
            {formatScore(sdiScore?.completeness_pct, 1)}%
          </div>
          <p className="text-[10px] text-slate-500 mt-1">
            {sdiScore?.participating_categories_count} of {sdiScore?.total_categories_count} Categories Active
          </p>
        </Card>

        <Card className="p-3">
          <span className="text-[10px] font-mono font-medium uppercase tracking-wider text-slate-400">
            Inspection Priority
          </span>
          <div className="text-2xl font-bold font-mono-numbers text-amber-600 dark:text-amber-400 mt-1">
            {formatScore(priorityScore?.priority_score)}
          </div>
          <p className="text-[10px] text-slate-500 mt-1">Tier: {priorityScore?.priority_level}</p>
        </Card>

        <Card className="p-3">
          <span className="text-[10px] font-mono font-medium uppercase tracking-wider text-slate-400">
            Unresolved Defect Reports
          </span>
          <div className="text-2xl font-bold font-mono-numbers text-rose-600 dark:text-rose-400 mt-1">
            {priorityScore?.unresolved_reports_count ?? 0}
          </div>
          <p className="text-[10px] text-slate-500 mt-1">Awaiting municipal repair</p>
        </Card>
      </div>

      {/* Category Component Weights Breakdown Table */}
      <Card>
        <CardHeader>
          <CardTitle>SDI Category Component Weights &amp; Defect Counts</CardTitle>
          <p className="text-xs text-slate-500">
            Deficiency contribution per infrastructure taxonomy category normalized across available observations.
          </p>
        </CardHeader>
        <CardContent>
          {sdiScore?.components && sdiScore.components.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Category</TableHead>
                  <TableHead>Observation Status</TableHead>
                  <TableHead>Defect Count</TableHead>
                  <TableHead>Category Score</TableHead>
                  <TableHead>Assigned Weight</TableHead>
                  <TableHead>Normalized Weight</TableHead>
                  <TableHead className="text-right">Weighted Contribution</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sdiScore.components.map((comp) => (
                  <TableRow key={comp.id}>
                    <TableCell>
                      <span className="font-semibold text-slate-900 dark:text-slate-100 block">
                        {comp.category.name}
                      </span>
                      <span className="text-[10px] text-slate-400">{comp.category.code}</span>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={
                          comp.availability_state === 'OBSERVED'
                            ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300'
                            : 'bg-slate-100 text-slate-500 dark:bg-slate-800'
                        }
                      >
                        {comp.availability_state}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-semibold">{comp.report_count}</TableCell>
                    <TableCell>{formatScore(comp.category_score)}</TableCell>
                    <TableCell>{(comp.assigned_weight * 100).toFixed(0)}%</TableCell>
                    <TableCell>
                      {comp.normalized_weight ? `${(comp.normalized_weight * 100).toFixed(1)}%` : '—'}
                    </TableCell>
                    <TableCell className="text-right font-bold text-indigo-600 dark:text-indigo-400">
                      {formatScore(comp.weighted_contribution)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="p-8 text-center text-xs text-slate-400">
              No category breakdowns computed yet. Click "Recalc SDI" to execute the engine.
            </div>
          )}
        </CardContent>
      </Card>

      {/* Historical Calculations Chart */}
      <Card>
        <CardHeader>
          <CardTitle>Historical SDI Score Progression</CardTitle>
          <p className="text-xs text-slate-500">
            Audit history of versioned SDI scoring runs for this administrative boundary.
          </p>
        </CardHeader>
        <CardContent>
          <div className="h-64 w-full">
            {historyChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={historyChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                  <XAxis dataKey="timestamp" tick={{ fontSize: 10 }} stroke="#94a3b8" />
                  <YAxis tick={{ fontSize: 10 }} stroke="#94a3b8" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'rgba(15, 23, 42, 0.9)',
                      border: '1px solid rgba(255,255,255,0.1)',
                      borderRadius: '0.75rem',
                      fontSize: '11px',
                      color: '#fff',
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="score"
                    stroke="#6366f1"
                    strokeWidth={2.5}
                    name="SDI Score"
                    dot={{ r: 4 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-slate-400">
                Awaiting multiple calculation checkpoints...
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
