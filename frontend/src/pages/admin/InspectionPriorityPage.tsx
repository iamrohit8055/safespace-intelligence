import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ListOrdered,
  Filter,
  RefreshCw,
  Eye,
  SlidersHorizontal,
} from 'lucide-react'
import { priorityApi } from '../../api/priority.api'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Select } from '../../components/ui/Select'
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '../../components/ui/Table'
import { formatScore, formatDate, formatPercentage } from '../../lib/utils'

export const InspectionPriorityPage: React.FC = () => {
  const [priorityFilter, setPriorityFilter] = useState<string>('')
  const [sortBy, setSortBy] = useState<string>('score_desc')

  const queryClient = useQueryClient()

  const { data: prioritiesData, isLoading } = useQuery({
    queryKey: ['area-priorities', priorityFilter, sortBy],
    queryFn: () =>
      priorityApi.listAreaPriorities({
        priority_level: priorityFilter || undefined,
        sort_by: sortBy,
        limit: 50,
      }),
  })

  const items = prioritiesData?.items || []

  return (
    <div className="space-y-4">
      {/* Title & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <ListOrdered className="h-4 w-4 text-sky-500" />
            <h1 className="text-base font-semibold tracking-tight text-slate-900 dark:text-slate-100">
              Inspection Priority Allocations
            </h1>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Ranked municipal field dispatch order calculated from defect severity, observation age, volume, and data completeness.
          </p>
        </div>
        <Button
          variant="outline"
          size="xs"
          onClick={() => queryClient.invalidateQueries({ queryKey: ['area-priorities'] })}
        >
          <RefreshCw className="h-3.5 w-3.5" />
          <span>Refresh Rankings</span>
        </Button>
      </div>

      {/* Filter toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-white dark:bg-slate-900 px-3 py-2.5 rounded-md border border-slate-200 dark:border-slate-800">
        <div className="flex items-center gap-2.5">
          <SlidersHorizontal className="h-3.5 w-3.5 text-slate-400" />
          <div className="w-44">
            <Select
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
            >
              <option value="">All Priority Tiers</option>
              <option value="CRITICAL">Critical Tier</option>
              <option value="HIGH">High Tier</option>
              <option value="MEDIUM">Medium Tier</option>
              <option value="LOW">Low Tier</option>
              <option value="INSUFFICIENT_DATA">Insufficient Data</option>
            </Select>
          </div>
          <div className="w-48">
            <Select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
            >
              <option value="score_desc">Highest Score First</option>
              <option value="score_asc">Lowest Score First</option>
              <option value="unresolved_desc">Most Unresolved Defects</option>
            </Select>
          </div>
        </div>

        <span className="text-[11px] font-mono text-slate-400">
          Showing {items.length} ranked administrative areas
        </span>
      </div>

      {/* Ranked Priority Table */}
      {items.length > 0 ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10">#</TableHead>
              <TableHead>Ward Area &amp; Code</TableHead>
              <TableHead>Priority Tier</TableHead>
              <TableHead className="text-right">Priority Score</TableHead>
              <TableHead className="text-right">SDI Index</TableHead>
              <TableHead className="text-right">Completeness</TableHead>
              <TableHead className="text-right">Unresolved</TableHead>
              <TableHead className="text-right">Confidence</TableHead>
              <TableHead>Last Inspection</TableHead>
              <TableHead className="text-right">Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item, index) => (
              <TableRow key={item.id}>
                <TableCell className="font-mono text-slate-400 text-xs">
                  {String(index + 1).padStart(2, '0')}
                </TableCell>
                <TableCell>
                  <Link
                    to={`/admin/areas/${item.area_id}`}
                    className="font-medium text-slate-900 dark:text-slate-100 hover:text-sky-600 dark:hover:text-sky-400"
                  >
                    {item.area_name || 'Ward Area'}
                  </Link>
                  <div className="text-[10px] font-mono text-slate-400 mt-0.5">
                    {item.area_code} &bull; {item.area_type?.toUpperCase()}
                  </div>
                </TableCell>
                <TableCell>
                  <Badge variant="priority" priority={item.priority_level} />
                </TableCell>
                <TableCell className="text-right font-mono-numbers font-semibold text-slate-900 dark:text-slate-100 text-sm">
                  {formatScore(item.priority_score)}
                </TableCell>
                <TableCell className="text-right font-mono-numbers font-medium text-sky-600 dark:text-sky-400">
                  {formatScore(item.sdi_score)}
                </TableCell>
                <TableCell className="text-right font-mono-numbers text-slate-600 dark:text-slate-300">
                  {formatPercentage(item.completeness_pct)}
                </TableCell>
                <TableCell className="text-right font-mono-numbers font-medium text-rose-600 dark:text-rose-400">
                  {item.unresolved_reports_count}
                </TableCell>
                <TableCell className="text-right font-mono-numbers text-slate-600 dark:text-slate-400">
                  {formatScore(item.confidence_score)}
                </TableCell>
                <TableCell className="text-[11px] font-mono text-slate-500 dark:text-slate-400">
                  {item.never_inspected ? 'Never Inspected' : formatDate(item.last_inspected_at, 'MMM d, yyyy')}
                </TableCell>
                <TableCell className="text-right">
                  <Link to={`/admin/areas/${item.area_id}`}>
                    <Button variant="outline" size="xs">
                      <Eye className="h-3 w-3 mr-1" /> Inspect
                    </Button>
                  </Link>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <div className="p-10 text-center rounded-md border border-dashed border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
          <ListOrdered className="h-8 w-8 text-slate-400 mx-auto mb-2" />
          <h3 className="text-xs font-semibold text-slate-800 dark:text-slate-200">
            No Priority Records Found
          </h3>
          <p className="text-[11px] text-slate-500 max-w-sm mx-auto mt-1">
            Inspection priorities will automatically calculate once municipal ward areas receive reports.
          </p>
        </div>
      )}
    </div>
  )
}
