import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  CopyCheck,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Sparkles,
  MapPin,
  Clock,
  ArrowRight,
} from 'lucide-react'
import { duplicatesApi } from '../../api/duplicates.api'
import { moderationApi } from '../../api/moderation.api'
import { useUIStore } from '../../stores/ui.store'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Modal } from '../../components/ui/Modal'
import { Textarea } from '../../components/ui/Textarea'
import { Select } from '../../components/ui/Select'
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '../../components/ui/Table'
import { formatDate } from '../../lib/utils'
import type { DuplicateCandidate } from '../../types'

export const DuplicateReviewPage: React.FC = () => {
  const [statusFilter, setStatusFilter] = useState<string>('PENDING')
  const [selectedCandidate, setSelectedCandidate] = useState<DuplicateCandidate | null>(null)
  const [decision, setDecision] = useState<'CONFIRMED_DUPLICATE' | 'NOT_DUPLICATE' | 'NEEDS_REVIEW'>('CONFIRMED_DUPLICATE')
  const [reason, setReason] = useState('')

  const queryClient = useQueryClient()
  const { addToast } = useUIStore()

  // Candidates list
  const { data: candidatesData, isLoading } = useQuery({
    queryKey: ['duplicate-candidates', statusFilter],
    queryFn: () =>
      duplicatesApi.listCandidates({
        review_status: statusFilter || undefined,
        limit: 50,
      }),
  })

  // Batch detection trigger mutation
  const detectMutation = useMutation({
    mutationFn: () => duplicatesApi.triggerDetection(),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['duplicate-candidates'] })
      addToast({
        type: 'success',
        title: 'Detection Executed',
        message: `Evaluated ${data.candidates_evaluated} pairs. Created ${data.new_candidates_created} new candidate matches.`,
      })
    },
    onError: (err: any) => {
      addToast({
        type: 'error',
        title: 'Detection Error',
        message: err.response?.data?.detail || 'Failed to trigger batch detection.',
      })
    },
  })

  // Review candidate mutation
  const reviewMutation = useMutation({
    mutationFn: () =>
      duplicatesApi.reviewCandidate(selectedCandidate!.id, {
        decision,
        reason,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['duplicate-candidates'] })
      setSelectedCandidate(null)
      setReason('')
      addToast({
        type: 'success',
        title: 'Duplicate Review Recorded',
        message: 'Review decision saved with canonical linking audit entry.',
      })
    },
    onError: (err: any) => {
      addToast({
        type: 'error',
        title: 'Review Error',
        message: err.response?.data?.detail || 'Failed to submit duplicate review.',
      })
    },
  })

  const candidates = candidatesData?.items || []

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <CopyCheck className="h-4 w-4 text-sky-500" />
            <h1 className="text-base font-semibold tracking-tight text-slate-900 dark:text-slate-100">
              Spatial Duplicate Deduplication
            </h1>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Audit proximity-matched candidate pairs to deduplicate defect reports and preserve SDI integrity.
          </p>
        </div>
        <Button
          variant="outline"
          size="xs"
          onClick={() => detectMutation.mutate()}
          isLoading={detectMutation.isPending}
        >
          <Sparkles className="h-3 w-3 mr-1 text-sky-500" />
          <span>Run Spatial Discovery</span>
        </Button>
      </div>

      {/* Filter toolbar */}
      <div className="flex items-center justify-between gap-3 bg-white dark:bg-slate-900 px-3 py-2 rounded-md border border-slate-200 dark:border-slate-800">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono uppercase text-slate-500">
            Review Status:
          </span>
          <div className="w-52">
            <Select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">All Candidates</option>
              <option value="PENDING">Pending Review</option>
              <option value="CONFIRMED_DUPLICATE">Confirmed Duplicate</option>
              <option value="NOT_DUPLICATE">Not a Duplicate</option>
              <option value="NEEDS_REVIEW">Needs Further Review</option>
            </Select>
          </div>
        </div>

        <span className="text-[11px] font-mono text-slate-400">
          {candidates.length} candidates
        </span>
      </div>

      {/* Table */}
      {candidates.length > 0 ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Candidate Pair (Report IDs)</TableHead>
              <TableHead>Spatial Separation</TableHead>
              <TableHead>Time Separation</TableHead>
              <TableHead>Review Status</TableHead>
              <TableHead>Discovered At</TableHead>
              <TableHead className="text-right">Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {candidates.map((cand) => (
              <TableRow key={cand.id}>
                <TableCell>
                  <div className="font-mono text-xs text-slate-800 dark:text-slate-200 font-medium">
                    {cand.first_report_id.slice(0, 8)}... &amp; {cand.second_report_id.slice(0, 8)}...
                  </div>
                  <div className="text-[10px] text-slate-400">Rule: {cand.rule_version}</div>
                </TableCell>
                <TableCell>
                  <span className="text-xs font-semibold text-indigo-600 dark:text-indigo-400">
                    {Number(cand.distance_metres).toFixed(1)} metres
                  </span>
                </TableCell>
                <TableCell className="text-xs text-slate-500">
                  {(cand.time_difference_seconds / 3600).toFixed(1)} hours
                </TableCell>
                <TableCell>
                  <Badge variant="status" status={cand.review_status} />
                </TableCell>
                <TableCell className="text-xs text-slate-500">
                  {formatDate(cand.detected_at)}
                </TableCell>
                <TableCell className="text-right">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setSelectedCandidate(cand)
                      setDecision('CONFIRMED_DUPLICATE')
                      setReason('')
                    }}
                  >
                    Review Pair
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <div className="p-12 text-center rounded-2xl border border-dashed border-slate-300 dark:border-slate-800 bg-white dark:bg-slate-900/40">
          <CopyCheck className="h-10 w-10 text-slate-400 mx-auto mb-3" />
          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
            No Duplicate Candidates Found
          </h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1 mb-4">
            No report pairs are currently flagged as spatial/temporal duplicates.
          </p>
          <Button
            size="sm"
            onClick={() => detectMutation.mutate()}
            isLoading={detectMutation.isPending}
          >
            Run Spatial Proximity Scan
          </Button>
        </div>
      )}

      {/* Review Modal */}
      {selectedCandidate && (
        <Modal
          isOpen={Boolean(selectedCandidate)}
          onClose={() => setSelectedCandidate(null)}
          title="Review Spatial Duplicate Match"
          description={`Proximity: ${Number(selectedCandidate.distance_metres).toFixed(1)}m apart`}
          size="lg"
        >
          <div className="space-y-4 text-xs">
            <div className="grid grid-cols-2 gap-3 p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40">
              <div>
                <span className="font-bold text-slate-700 dark:text-slate-300 block">Report A</span>
                <span className="font-mono text-[11px] text-slate-500">{selectedCandidate.first_report_id}</span>
              </div>
              <div>
                <span className="font-bold text-slate-700 dark:text-slate-300 block">Report B</span>
                <span className="font-mono text-[11px] text-slate-500">{selectedCandidate.second_report_id}</span>
              </div>
            </div>

            <Select
              label="Moderation Decision"
              value={decision}
              onChange={(e) => setDecision(e.target.value as any)}
            >
              <option value="CONFIRMED_DUPLICATE">CONFIRMED DUPLICATE (Link Duplicate to Canonical Report)</option>
              <option value="NOT_DUPLICATE">NOT A DUPLICATE (Distinct Physical Deficiencies)</option>
              <option value="NEEDS_REVIEW">NEEDS REVIEW (Requires On-Site Verification)</option>
            </Select>

            <Textarea
              label="Moderation Justification (Mandatory, minimum 5 characters)"
              placeholder="Explain physical grounds for duplicate confirmation or separation..."
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              required
            />

            <div className="flex justify-end gap-2 pt-3 border-t border-slate-200 dark:border-slate-800">
              <Button variant="outline" onClick={() => setSelectedCandidate(null)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                disabled={reason.trim().length < 5}
                isLoading={reviewMutation.isPending}
                onClick={() => reviewMutation.mutate()}
              >
                Submit Decision
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
