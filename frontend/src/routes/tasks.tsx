import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { RefreshCw } from 'lucide-react'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Label } from '../components/ui/label'
import { Select } from '../components/ui/select'
import { requirementsApi, errorMessage } from '../lib/requirements-api'
import { platformApi } from '../lib/platform-api'

export const Route = createFileRoute('/tasks')({ component: Tasks })

function Tasks() {
  const queryClient = useQueryClient()
  const [filter, setFilter] = useState('all')
  const tasks = useQuery({
    queryKey: ['all-tasks'],
    queryFn: platformApi.tasks,
    refetchInterval: 2000,
  })
  const cancel = useMutation({
    mutationFn: requirementsApi.cancel,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['all-tasks'] }),
  })
  const allTasks = tasks.data?.tasks ?? []
  const visible = allTasks.filter((task) => filter === 'all' || task.status === filter)
  return <div className="space-y-6">
    <header className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 className="text-3xl font-bold">Tasks Monitor</h2>
        <p>Monitor and manage document processing tasks</p>
      </div>
      <Button variant="ghost" disabled={tasks.isFetching} onClick={() => tasks.refetch()}>
        <RefreshCw className="mr-2 h-4 w-4" />Refresh
      </Button>
    </header>
    {tasks.isError && <p role="alert">{errorMessage(tasks.error)}</p>}
    {cancel.isError && <p role="alert">{errorMessage(cancel.error)}</p>}
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
      {[
        { label: 'Total', value: tasks.data?.total_count, color: '' },
        { label: 'Running', status: 'running', color: 'text-blue-600' },
        { label: 'Pending', status: 'pending', color: 'text-amber-600' },
        { label: 'Success', status: 'success', color: 'text-green-600' },
        { label: 'Failed', status: 'failed', color: 'text-red-600' },
      ].map(({ label, value, status, color }) => (
        <Card key={label}><CardContent className="p-6">
          <p className="text-sm">{label}</p>
          <p className={`mt-2 text-2xl font-semibold ${color}`}>
            {tasks.data ? value ?? allTasks.filter((task) => task.status === status).length : '—'}
          </p>
        </CardContent></Card>
      ))}
    </div>
    {tasks.data && tasks.data.total_count > allTasks.length && (
      <p role="note">Status counts and the recent list cover the latest {allTasks.length} tasks; Total includes all saved tasks.</p>
    )}
    <Card>
      <CardHeader className="flex-row flex-wrap items-center justify-between gap-3 space-y-0">
        <div><CardTitle>Recent Tasks</CardTitle><p className="mt-1 text-sm">All processing tasks</p></div>
        <div className="flex items-center gap-2">
          <Label htmlFor="task-filter">Filter:</Label>
          <Select id="task-filter" value={filter} onChange={(event) => setFilter(event.target.value)}>
            {['all', 'pending', 'running', 'success', 'failed', 'cancelled'].map((status) => (
              <option key={status} value={status}>{status[0].toUpperCase() + status.slice(1)}</option>
            ))}
          </Select>
        </div>
      </CardHeader>
      <CardContent>
        {tasks.isPending && <p className="py-12 text-center">Loading tasks...</p>}
        {tasks.data && visible.length === 0 && <p className="py-12 text-center">No tasks found</p>}
        {visible.map((task) => <article key={task.task_id} className="border-t py-4 space-y-2">
          <p className="break-all">{task.task_id}</p>
          <p>{task.status}: {task.message}</p>
          <progress aria-label={`Progress for ${task.task_id}`} className="w-full" max={100} value={task.progress} />
          {task.error && <p role="alert">{task.error}</p>}
          {task.result?.repo_id && <p>Indexed repository ID: {task.result.repo_id}</p>}
          {task.metadata?.kind === 'analysis' && <Link className="underline" to="/repositories" search={{ task: task.task_id }}>Open analysis</Link>}
          {(task.status === 'pending' || task.status === 'running') &&
            <Button variant="outline" disabled={cancel.isPending} onClick={() => cancel.mutate(task.task_id)}>Cancel</Button>}
        </article>)}
      </CardContent>
    </Card>
  </div>
}