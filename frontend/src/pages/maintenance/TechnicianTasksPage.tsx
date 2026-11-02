import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Wrench,
  CheckCircle2,
  Play,
  Pause,
  AlertTriangle,
  Clock,
  Eye,
  MapPin,
  CheckCheck,
} from 'lucide-react'
import { maintenanceApi } from '../../api/maintenance.api'
import { useUIStore } from '../../stores/ui.store'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Modal } from '../../components/ui/Modal'
import { Textarea } from '../../components/ui/Textarea'
import { Select } from '../../components/ui/Select'
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '../../components/ui/Table'
import { formatDate } from '../../lib/utils'
import type { MaintenanceTask } from '../../types'

export const TechnicianTasksPage: React.FC = () => {
  const queryClient = useQueryClient()
  const { addToast } = useUIStore()

  const [statusFilter, setStatusFilter] = useState<string>('')
  const [selectedTask, setSelectedTask] = useState<MaintenanceTask | null>(null)
  const [isBlockModalOpen, setIsBlockModalOpen] = useState(false)
  const [isCompleteModalOpen, setIsCompleteModalOpen] = useState(false)
  const [actionNotes, setActionNotes] = useState('')

  const { data: myTasksData, isLoading } = useQuery({
    queryKey: ['my-technician-tasks', statusFilter],
    queryFn: () =>
      maintenanceApi.getMyTasks({
        status: statusFilter || undefined,
        limit: 50,
      }),
  })

  // Mutations
  const acceptMutation = useMutation({
    mutationFn: (taskId: string) => maintenanceApi.acceptTask(taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['my-technician-tasks'] })
      addToast({
        type: 'info',
        title: 'Task Accepted',
        message: 'Work order accepted. Ready to commence field repair.',
      })
    },
    onError: (err: any) => {
      addToast({
        type: 'error',
        title: 'Accept Failed',
        message: err.response?.data?.detail || 'Could not accept task.',
      })
    },
  })

  const startMutation = useMutation({
    mutationFn: (taskId: string) => maintenanceApi.startTask(taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['my-technician-tasks'] })
      addToast({
        type: 'info',
        title: 'Work Started',
        message: 'Task transitioned to IN_PROGRESS.',
      })
    },
    onError: (err: any) => {
      addToast({
        type: 'error',
        title: 'Start Failed',
        message: err.response?.data?.detail || 'Could not start task.',
      })
    },
  })

  const blockMutation = useMutation({
    mutationFn: () =>
      maintenanceApi.blockTask(selectedTask!.id, actionNotes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['my-technician-tasks'] })
      setIsBlockModalOpen(false)
      setSelectedTask(null)
      setActionNotes('')
      addToast({
        type: 'warning',
        title: 'Task Marked Blocked',
        message: 'Impediment logged. Supervisors notified.',
      })
    },
    onError: (err: any) => {
      addToast({
        type: 'error',
        title: 'Action Failed',
        message: err.response?.data?.detail || 'Failed to block task.',
      })
    },
  })

  const completeMutation = useMutation({
    mutationFn: () =>
      maintenanceApi.completeTask(selectedTask!.id, actionNotes || undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['my-technician-tasks'] })
      setIsCompleteModalOpen(false)
      setSelectedTask(null)
      setActionNotes('')
      addToast({
        type: 'success',
        title: 'Repair Completed',
        message: 'Deficiency resolution verified and recorded.',
      })
    },
    onError: (err: any) => {
      addToast({
        type: 'error',
        title: 'Completion Failed',
        message: err.response?.data?.detail || 'Could not complete task.',
      })
    },
  })

  const tasks = myTasksData?.items || []

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#829783]/25 dark:border-[#829783]/20">
        <div>
          <span className="text-[10px] font-mono uppercase tracking-widest text-[#C36B48] font-semibold block">
            Field Operations
          </span>
          <div className="flex items-center gap-2 mt-0.5">
            <Wrench className="h-4 w-4 text-[#C36B48]" />
            <h1 className="font-serif-headline text-xl sm:text-2xl font-normal tracking-tight text-[#18372C] dark:text-[#F5F2EA]">
              Field Maintenance Work Orders
            </h1>
          </div>
          <p className="text-xs text-[#73766F] dark:text-[#829783] mt-0.5">
            Accept assigned infrastructure repairs, document on-site blockers, and log work order completion.
          </p>
        </div>
      </div>

      {/* Filter toolbar */}
      <div className="flex items-center justify-between gap-3 bg-[#FFFEFA] dark:bg-[#1E211E] px-3 py-2 rounded-sm border border-[#829783]/30">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono uppercase text-slate-500">
            Status:
          </span>
          <div className="w-52">
            <Select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">All Work Orders</option>
              <option value="ASSIGNED">Assigned</option>
              <option value="ACCEPTED">Accepted</option>
              <option value="IN_PROGRESS">In Progress</option>
              <option value="BLOCKED">Blocked</option>
              <option value="COMPLETED">Completed</option>
            </Select>
          </div>
        </div>

        <span className="text-[11px] font-mono text-slate-400">
          {tasks.length} tasks
        </span>
      </div>

      {/* Tasks Table */}
      {tasks.length > 0 ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Work Order</TableHead>
              <TableHead>Priority</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Created At</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {tasks.map((task) => (
              <TableRow key={task.id}>
                <TableCell>
                  <span className="font-semibold text-slate-900 dark:text-slate-100 block">
                    {task.title}
                  </span>
                  {task.description && (
                    <span className="text-xs text-slate-500 block truncate max-w-sm">
                      {task.description}
                    </span>
                  )}
                </TableCell>
                <TableCell>
                  <Badge variant="priority" priority={task.priority} />
                </TableCell>
                <TableCell>
                  <Badge variant="status" status={task.status} />
                </TableCell>
                <TableCell className="text-xs text-slate-500">
                  {formatDate(task.created_at)}
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex items-center justify-end gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setSelectedTask(task)}
                    >
                      <Eye className="h-3.5 w-3.5 mr-1" /> View
                    </Button>

                    {task.status === 'ASSIGNED' && (
                      <Button
                        variant="primary"
                        size="sm"
                        isLoading={acceptMutation.isPending}
                        onClick={() => acceptMutation.mutate(task.id)}
                      >
                        <CheckCircle2 className="h-3.5 w-3.5 mr-1" /> Accept
                      </Button>
                    )}

                    {(task.status === 'ACCEPTED' || task.status === 'BLOCKED') && (
                      <Button
                        variant="primary"
                        size="sm"
                        className="bg-indigo-600 hover:bg-indigo-700"
                        isLoading={startMutation.isPending}
                        onClick={() => startMutation.mutate(task.id)}
                      >
                        <Play className="h-3.5 w-3.5 mr-1" /> Start Work
                      </Button>
                    )}

                    {(task.status === 'ACCEPTED' || task.status === 'IN_PROGRESS') && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="text-amber-600 border-amber-300 hover:bg-amber-50"
                        onClick={() => {
                          setSelectedTask(task)
                          setIsBlockModalOpen(true)
                        }}
                      >
                        <Pause className="h-3.5 w-3.5 mr-1" /> Block
                      </Button>
                    )}

                    {task.status === 'IN_PROGRESS' && (
                      <Button
                        variant="primary"
                        size="sm"
                        className="bg-emerald-600 hover:bg-emerald-700"
                        onClick={() => {
                          setSelectedTask(task)
                          setIsCompleteModalOpen(true)
                        }}
                      >
                        <CheckCheck className="h-3.5 w-3.5 mr-1" /> Complete
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <div className="p-12 text-center rounded-2xl border border-dashed border-slate-300 dark:border-slate-800 bg-white dark:bg-slate-900/40">
          <Wrench className="h-10 w-10 text-slate-400 mx-auto mb-3" />
          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
            No Assigned Work Orders
          </h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1">
            You currently have no maintenance tasks assigned to your queue.
          </p>
        </div>
      )}

      {/* Task Inspection Modal */}
      {selectedTask && !isBlockModalOpen && !isCompleteModalOpen && (
        <Modal
          isOpen={Boolean(selectedTask)}
          onClose={() => setSelectedTask(null)}
          title={selectedTask.title}
          description={`Work Order ID: ${selectedTask.id}`}
        >
          <div className="space-y-4 text-xs">
            <div className="flex items-center justify-between">
              <Badge variant="status" status={selectedTask.status} />
              <Badge variant="priority" priority={selectedTask.priority} />
            </div>

            <div>
              <span className="font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Instructions &amp; Description:
              </span>
              <p className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-200 leading-relaxed whitespace-pre-wrap">
                {selectedTask.description || 'No specific technical instructions provided.'}
              </p>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-slate-200 dark:border-slate-800">
              <Button variant="outline" onClick={() => setSelectedTask(null)}>
                Close
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Block Task Modal */}
      {selectedTask && isBlockModalOpen && (
        <Modal
          isOpen={isBlockModalOpen}
          onClose={() => setIsBlockModalOpen(false)}
          title="Flag Work Order as Blocked"
          description={`Task: "${selectedTask.title}"`}
        >
          <div className="space-y-4 text-xs">
            <Textarea
              label="Blocker Reason &amp; Impediments (Mandatory)"
              placeholder="e.g. Awaiting specialized replacement wiring, road access blocked by construction..."
              rows={3}
              value={actionNotes}
              onChange={(e) => setActionNotes(e.target.value)}
              required
            />

            <div className="flex justify-end gap-2 pt-3 border-t border-slate-200 dark:border-slate-800">
              <Button variant="outline" onClick={() => setIsBlockModalOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="danger"
                disabled={actionNotes.trim().length < 3}
                isLoading={blockMutation.isPending}
                onClick={() => blockMutation.mutate()}
              >
                Confirm Blocked
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Complete Task Modal */}
      {selectedTask && isCompleteModalOpen && (
        <Modal
          isOpen={isCompleteModalOpen}
          onClose={() => setIsCompleteModalOpen(false)}
          title="Verify &amp; Complete Repair"
          description={`Task: "${selectedTask.title}"`}
        >
          <div className="space-y-4 text-xs">
            <p className="text-slate-600 dark:text-slate-300">
              Confirm that on-site physical repair work is complete and the infrastructure defect has been resolved.
            </p>

            <Textarea
              label="Completion Notes (Optional)"
              placeholder="e.g. Luminaire replaced with 45W LED fixture, tested and operational..."
              rows={3}
              value={actionNotes}
              onChange={(e) => setActionNotes(e.target.value)}
            />

            <div className="flex justify-end gap-2 pt-3 border-t border-slate-200 dark:border-slate-800">
              <Button variant="outline" onClick={() => setIsCompleteModalOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                className="bg-emerald-600 hover:bg-emerald-700"
                isLoading={completeMutation.isPending}
                onClick={() => completeMutation.mutate()}
              >
                Mark Repair Complete
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
