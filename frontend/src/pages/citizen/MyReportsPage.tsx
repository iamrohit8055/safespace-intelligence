import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { PlusCircle, FileText, Filter, Eye } from 'lucide-react'
import { reportsApi } from '../../api/reports.api'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Select } from '../../components/ui/Select'
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '../../components/ui/Table'
import { formatDate } from '../../lib/utils'

export const MyReportsPage: React.FC = () => {
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [page, setPage] = useState(0)
  const limit = 10

  const { data, isLoading } = useQuery({
    queryKey: ['my-reports', statusFilter, page],
    queryFn: () =>
      reportsApi.getMyReports({
        status: statusFilter || undefined,
        limit,
        offset: page * limit,
      }),
  })

  const reports = data?.items || []
  const total = data?.total || 0
  const totalPages = Math.ceil(total / limit)

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-200 dark:border-slate-800">
        <div>
          <h1 className="text-base font-semibold tracking-tight text-slate-900 dark:text-slate-100">
            My Infrastructure Submissions
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Track verification status, assigned ward, and resolution progress for your reports.
          </p>
        </div>
        <Link to="/citizen/submit">
          <Button variant="primary" size="sm">
            <PlusCircle className="h-3.5 w-3.5 mr-1" />
            Report New Deficiency
          </Button>
        </Link>
      </div>

      {/* Filter Toolbar */}
      <div className="flex items-center justify-between gap-3 bg-white dark:bg-slate-900 px-3 py-2 rounded-md border border-slate-200 dark:border-slate-800">
        <div className="flex items-center gap-2">
          <Filter className="h-3.5 w-3.5 text-slate-400" />
          <div className="w-44">
            <Select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value)
                setPage(0)
              }}
            >
              <option value="">All Statuses</option>
              <option value="SUBMITTED">Submitted</option>
              <option value="UNDER_VERIFICATION">Under Verification</option>
              <option value="VERIFIED">Verified</option>
              <option value="REJECTED">Rejected</option>
            </Select>
          </div>
        </div>

        <span className="text-[11px] font-mono text-slate-400">
          {total} total submissions
        </span>
      </div>

      {/* Reports Table */}
      {reports.length > 0 ? (
        <div className="space-y-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Title & Category</TableHead>
                <TableHead>Ward Area</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Observed Date</TableHead>
                <TableHead className="text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {reports.map((report) => (
                <TableRow key={report.id}>
                  <TableCell>
                    <div className="font-semibold text-slate-900 dark:text-slate-100">
                      {report.title}
                    </div>
                    <div className="text-xs text-slate-500">
                      {report.category.name} ({report.category.code})
                    </div>
                  </TableCell>
                  <TableCell>
                    <span className="text-xs font-medium">
                      {report.administrative_area?.name || 'Unassigned'}
                    </span>
                  </TableCell>
                  <TableCell>
                    <Badge variant="status" status={report.status} />
                  </TableCell>
                  <TableCell className="text-xs text-slate-500">
                    {formatDate(report.observed_at)}
                  </TableCell>
                  <TableCell className="text-right">
                    <Link to={`/citizen/reports/${report.id}`}>
                      <Button variant="outline" size="sm">
                        <Eye className="h-3.5 w-3.5 mr-1" />
                        Details
                      </Button>
                    </Link>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between text-xs text-slate-500 px-2">
              <span>
                Showing {page * limit + 1}–{Math.min((page + 1) * limit, total)} of {total}
              </span>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={page === 0}
                  onClick={() => setPage(page - 1)}
                >
                  Previous
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={page >= totalPages - 1}
                  onClick={() => setPage(page + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="p-12 text-center rounded-2xl border border-dashed border-slate-300 dark:border-slate-800 bg-white dark:bg-slate-900/50">
          <FileText className="h-10 w-10 text-slate-400 mx-auto mb-3" />
          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
            No Reports Found
          </h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1 mb-4">
            No infrastructure reports match your current filter.
          </p>
          <Link to="/citizen/submit">
            <Button size="sm">Submit Report</Button>
          </Link>
        </div>
      )}
    </div>
  )
}
