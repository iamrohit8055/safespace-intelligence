import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Wrench,
  PlusCircle,
  UserPlus,
  XCircle,
  Clock,
  History,
  CheckCircle2,
  AlertTriangle,
  Filter,
} from 'lucide-react'
import { maintenanceApi } from '../../api/maintenance.api'
import { moderationApi } from '../../api/moderation.api'
import { useUIStore } from '../../stores/ui.store'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { Textarea } from '../../components/ui/Textarea'
import { Select } from '../../components/ui/Select'
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '../../components/ui/Table'
import { formatDate } from '../../lib/utils'
import type { MaintenanceTask, MaintenanceTaskEvent } from '../../types'

export const AdminMaintenancePage: React.FC = () => {
  const queryClient = useQueryClient()
  const { addToast } = useUIStore()

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [priorityFilter, setPriorityFilter] = useState<string>('')

  // Modals state
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [selectedTask, setSelectedTask] = useState<MaintenanceTask | null>(null)
  const [isAssignOpen, setIsAssignOpen] = useState(false)
  const [isCancelOpen, setIsCancelOpen] = useState(false)
  const [isHistoryOpen, setIsHistoryOpen] = useState(false)

  // Create task state
  const [reportId, setReportId] = useState('')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState<'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'>('MEDIUM')
  const [assignTechnicianId, setAssignTechnicianId] = useState('')

  // Action state
  const [targetTechId, setTargetTechId] = useState('')
  const [actionNotes, setActionNotes] = useState('')

  // Queries
  const { data: tasksData, isLoading } = useQuery({
    queryKey: ['admin-maintenance-tasks', statusFilter, priorityFilter],
    queryFn: () =>
      maintenanceApi.listTasks({
        status: statusFilter || undefined,
        priority: priorityFilter || undefined,
        limit: 50,
      }),
  })

  const { data: technicians = [] } = useQuery({
    queryKey: ['maintenance-technicians'],
    queryFn: maintenanceApi.listTechnicians,
  })

  const { data: verifiedReportsData } = useQuery({
    queryKey: ['verified-reports-for-task'],
    queryFn: () => moderationApi.listReports({ status: 'VERIFIED', limit: 30 }),
    enabled: isCreateOpen,
  })

  const { data: taskHistory = [] } = useQuery({
    queryKey: ['task-history', selectedTask?.id],
    queryFn: () => maintenanceApi.getTaskHistory(selectedTask!.id),
    enabled: Boolean(selectedTask && isHistoryOpen),
  })

  // Mutations
  const createTaskMutation = useMutation({
    mutationFn: () =>
      maintenanceApi.createTask({
        report_id: reportId,
        title,
        description,
        priority,
        assigned_to_id: assignTechnicianId || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-maintenance-tasks'] })
      setIsCreateOpen(false)
      setTitle('')
      setDescription('')
      setReportId('')
      setAssignTechnicianId('')
      addToast({
        type: 'success',
        title: 'Work Order Created',
        message: 'Maintenance task dispatched successfully.',
      })
    },
    onError: (err: any) => {
      addToast({
        type: 'error',
        title: 'Creation Failed',
        message: err.response?.data?.detail || 'Failed to create work order.',
      })
    },
  })

  const assignTaskMutation = useMutation({
    mutationFn: () =>
      maintenanceApi.assignTask(selectedTask!.id, targetTechId, actionNotes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-maintenance-tasks'] })
      setIsAssignOpen(false)
      setSelectedTask(null)
      setActionNotes('')
      addToast({
        type: 'success',
        title: 'Task Assigned',
        message: 'Technician assigned with status updated to ASSIGNED.',
      })
    },
    onError: (err: any) => {
      addToast({
        type: 'error',
        title: 'Assignment Failed',
        message: err.response?.data?.detail || 'Failed to assign technician.',
      })
    },
  })

  const cancelTaskMutation = useMutation({
    mutationFn: () =>
      maintenanceApi.cancelTask(selectedTask!.id, actionNotes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-maintenance-tasks'] })
      setIsCancelOpen(false)
      setSelectedTask(null)
      setActionNotes('')
      addToast({
        type: 'info',
        title: 'Task Cancelled',
        message: 'Maintenance task has been cancelled.',
      })
    },
    onError: (err: any) => {
      addToast({
        type: 'error',
        title: 'Cancellation Failed',
        message: err.response?.data?.detail || 'Failed to cancel task.',
      })
    },
  })

  const tasks = tasksData?.items || []

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <Wrench className="h-4 w-4 text-sky-500" />
            <h1 className="text-base font-semibold tracking-tight text-slate-900 dark:text-slate-100">
              Maintenance Operations &amp; Work Orders
            </h1>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Create repair work orders from verified physical defects, assign field technicians, and audit completion timelines.
          </p>
        </div>
        <Button variant="primary" size="sm" onClick={() => setIsCreateOpen(true)}>
          <PlusCircle className="h-3.5 w-3.5 mr-1" /> Create Work Order
        </Button>
      </div>

      {/* Filter toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-white dark:bg-slate-900 px-3 py-2 rounded-md border border-slate-200 dark:border-slate-800">
        <div className="flex items-center gap-2">
          <Filter className="h-3.5 w-3.5 text-slate-400" />
          <div className="w-44">
            <Select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">All Statuses</option>
              <option value="CREATED">Created</option>
              <option value="ASSIGNED">Assigned</option>
              <option value="ACCEPTED">Accepted</option>
              <option value="IN_PROGRESS">In Progress</option>
              <option value="BLOCKED">Blocked</option>
              <option value="COMPLETED">Completed</option>
              <option value="CANCELLED">Cancelled</option>
            </Select>
          </div>
          <div className="w-40">
            <Select
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
            >
              <option value="">All Priorities</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </Select>
          </div>
        </div>

        <span className="text-[11px] font-mono text-slate-400">
          {tasks.length} active work orders
        </span>
      </div>

      {/* Tasks Table */}
      {tasks.length > 0 ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Work Order Title</TableHead>
              <TableHead>Priority</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Assigned Technician</TableHead>
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
                    <span className="text-xs text-slate-500 truncate block max-w-xs">
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
                <TableCell>
                  {task.assigned_to ? (
                    <span className="text-xs font-medium text-slate-800 dark:text-slate-200">
                      {task.assigned_to.full_name}
                    </span>
                  ) : (
                    <span className="text-xs text-amber-600 font-medium">Unassigned</span>
                  )}
                </TableCell>
                <TableCell className="text-xs text-slate-500">
                  {formatDate(task.created_at)}
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex items-center justify-end gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setSelectedTask(task)
                        setIsHistoryOpen(true)
                      }}
                    >
                      <History className="h-3.5 w-3.5 mr-1" /> History
                    </Button>

                    {task.status !== 'COMPLETED' && task.status !== 'CANCELLED' && (
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => {
                          setSelectedTask(task)
                          setTargetTechId(task.assigned_to_id || '')
                          setIsAssignOpen(true)
                        }}
                      >
                        <UserPlus className="h-3.5 w-3.5 mr-1" />
                        {task.assigned_to_id ? 'Reassign' : 'Assign'}
                      </Button>
                    )}

                    {task.status !== 'COMPLETED' && task.status !== 'CANCELLED' && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-rose-600 hover:text-rose-700 hover:bg-rose-50"
                        onClick={() => {
                          setSelectedTask(task)
                          setIsCancelOpen(true)
                        }}
                      >
                        <XCircle className="h-3.5 w-3.5" />
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
            No Maintenance Tasks Found
          </h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1 mb-4">
            No active work orders match your current filter criteria.
          </p>
          <Button size="sm" onClick={() => setIsCreateOpen(true)}>
            Create New Work Order
          </Button>
        </div>
      )}

      {/* Create Task Modal */}
      <Modal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title="Create Maintenance Work Order"
        description="Link a verified infrastructure defect to an actionable repair work order."
        size="lg"
      >
        <div className="space-y-4 text-xs">
          <div>
            <label className="font-semibold text-slate-700 dark:text-slate-300 block mb-1">
              Select Verified Deficiency Report
            </label>
            <select
              className="flex h-10 w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              value={reportId}
              onChange={(e) => {
                setReportId(e.target.value)
                const rep = verifiedReportsData?.items.find((r) => r.id === e.target.value)
                if (rep) {
                  setTitle(`Repair: ${rep.title}`)
                  setDescription(`Deficiency in ${rep.administrative_area?.name || 'Area'}: ${rep.description}`)
                }
              }}
              required
            >
              <option value="">-- Choose a verified report --</option>
              {verifiedReportsData?.items.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.title} ({r.category.name} &bull; {r.administrative_area?.name || 'Unassigned'})
                </option>
              ))}
            </select>
          </div>

          <Input
            label="Work Order Title"
            placeholder="e.g. Streetlight luminaire replacement"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
          />

          <Textarea
            label="Repair Description &amp; Instructions"
            placeholder="Field repair specifications, required tools, replacement parts..."
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />

          <div className="grid grid-cols-2 gap-3">
            <Select
              label="Priority Level"
              value={priority}
              onChange={(e) => setPriority(e.target.value as any)}
            >
              <option value="LOW">Low</option>
              <option value="MEDIUM">Medium</option>
              <option value="HIGH">High</option>
              <option value="CRITICAL">Critical</option>
            </Select>

            <Select
              label="Assign Technician (Optional)"
              value={assignTechnicianId}
              onChange={(e) => setAssignTechnicianId(e.target.value)}
            >
              <option value="">-- Leave Unassigned --</option>
              {technicians.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.full_name} ({t.email})
                </option>
              ))}
            </Select>
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-slate-200 dark:border-slate-800">
            <Button variant="outline" onClick={() => setIsCreateOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              disabled={!reportId || !title}
              isLoading={createTaskMutation.isPending}
              onClick={() => createTaskMutation.mutate()}
            >
              Dispatch Work Order
            </Button>
          </div>
        </div>
      </Modal>

      {/* Assign Technician Modal */}
      {selectedTask && isAssignOpen && (
        <Modal
          isOpen={isAssignOpen}
          onClose={() => setIsAssignOpen(false)}
          title="Assign Maintenance Work Order"
          description={`Task: "${selectedTask.title}"`}
        >
          <div className="space-y-4 text-xs">
            <Select
              label="Designated Technician"
              value={targetTechId}
              onChange={(e) => setTargetTechId(e.target.value)}
              required
            >
              <option value="">-- Select a Technician --</option>
              {technicians.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.full_name} ({t.email})
                </option>
              ))}
            </Select>

            <Textarea
              label="Assignment Notes (Optional)"
              placeholder="Instructions, access keys, safety warnings..."
              rows={2}
              value={actionNotes}
              onChange={(e) => setActionNotes(e.target.value)}
            />

            <div className="flex justify-end gap-2 pt-3 border-t border-slate-200 dark:border-slate-800">
              <Button variant="outline" onClick={() => setIsAssignOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                disabled={!targetTechId}
                isLoading={assignTaskMutation.isPending}
                onClick={() => assignTaskMutation.mutate()}
              >
                Confirm Assignment
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Cancel Task Modal */}
      {selectedTask && isCancelOpen && (
        <Modal
          isOpen={isCancelOpen}
          onClose={() => setIsCancelOpen(false)}
          title="Cancel Maintenance Task"
          description={`Task: "${selectedTask.title}"`}
        >
          <div className="space-y-4 text-xs">
            <Textarea
              label="Cancellation Reason (Mandatory)"
              placeholder="Explain why this work order is being cancelled..."
              rows={3}
              value={actionNotes}
              onChange={(e) => setActionNotes(e.target.value)}
              required
            />

            <div className="flex justify-end gap-2 pt-3 border-t border-slate-200 dark:border-slate-800">
              <Button variant="outline" onClick={() => setIsCancelOpen(false)}>
                Go Back
              </Button>
              <Button
                variant="danger"
                disabled={actionNotes.trim().length < 3}
                isLoading={cancelTaskMutation.isPending}
                onClick={() => cancelTaskMutation.mutate()}
              >
                Cancel Work Order
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* History Audit Drawer/Modal */}
      {selectedTask && isHistoryOpen && (
        <Modal
          isOpen={isHistoryOpen}
          onClose={() => setIsHistoryOpen(false)}
          title="Work Order Audit Timeline"
          description={`Task: "${selectedTask.title}"`}
          size="md"
        >
          <div className="space-y-3 text-xs">
            {taskHistory.length > 0 ? (
              <div className="space-y-3">
                {taskHistory.map((event) => (
                  <div
                    key={event.id}
                    className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 space-y-1"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-800 dark:text-slate-200">
                        {event.from_status ? `${event.from_status} → ${event.to_status}` : event.to_status}
                      </span>
                      <span className="text-[10px] text-slate-400">
                        {formatDate(event.created_at)}
                      </span>
                    </div>
                    {event.notes && (
                      <p className="text-slate-600 dark:text-slate-300">{event.notes}</p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-6 text-center text-slate-400">
                No status events recorded yet.
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  )
}
