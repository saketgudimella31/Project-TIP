import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { Activity, CircleAlert, Database, Server } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { errorMessage } from '../lib/requirements-api'
import { platformApi, serviceState } from '../lib/platform-api'

export const Route = createFileRoute('/')({ component: Dashboard })

function Dashboard() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: platformApi.health,
    refetchInterval: 10000,
  })
  const services = [
    { title: 'SQLite Analysis Storage', icon: Database, state: serviceState(health.data, ['sqlite_connected']), on: 'Connected', off: 'Unavailable' },
    { title: 'RAG Retrieval', icon: Activity, state: serviceState(health.data, ['local_retrieval']), on: 'Local retrieval available', off: 'Unavailable' },
    { title: 'Task Queue', icon: Server, state: serviceState(health.data, ['task_queue', 'celery']), on: 'Running', off: 'Stopped' },
  ]
  return <div className="space-y-6">
    <header>
      <h2 className="text-3xl font-bold">Dashboard</h2>
      <p>Monitor the requirements analysis platform</p>
    </header>
    {health.isError && <p role="alert">{errorMessage(health.error)}</p>}
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle>System Status</CardTitle>
          <p className="mt-1 text-sm">Overall system health and services</p>
        </div>
        <span className="inline-flex items-center gap-1 text-sm">
          <CircleAlert className="h-4 w-4" />
          {health.isPending ? 'Connecting...' : health.data?.status ?? 'Unavailable'}
        </span>
      </CardHeader>
      <CardContent className="grid gap-4 md:grid-cols-3">
        {services.map(({ title, icon: Icon, state, on, off }) => (
          <div className="flex items-center gap-4 rounded-lg border p-4" key={title}>
            <div className={`rounded-full p-3 ${state === true ? 'bg-green-100 text-green-600' : state === false ? 'bg-red-100 text-red-600' : 'bg-gray-100 text-gray-600'}`}>
              <Icon className="h-6 w-6" />
            </div>
            <div className="text-sm">
              <p className="font-medium">{title}</p>
              <p className="text-xs">{state === undefined ? 'Not reported by backend' : state ? on : off}</p>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
    {health.data && (
      <p className="text-sm" role="status">
        AI gateway endpoint: {health.data.services.gateway_configured ? 'Configured' : 'Not configured'}
        {' · '}Authentication: {health.data.services.gateway_auth_configured ? 'Configured (not verified)' : 'Not configured'}
        {' · '}Graph impact: {health.data.services.graph_service ? 'Connected' : 'Not configured'}
      </p>
    )}
    <div className="grid gap-4 md:grid-cols-3">
      {([
        { to: '/tasks', title: 'View Tasks', text: 'Monitor processing tasks and queue status' },
        { to: '/repositories', title: 'Manage Repositories', text: 'Ingest and manage code repositories' },
        { to: '/metrics', title: 'View Metrics', text: 'System performance and statistics' },
      ] as const).map(({ to, title, text }) => (
        <Link key={to} to={to} className="rounded-lg border p-6 shadow-sm hover:bg-accent">
          <h3 className="font-semibold">{title}</h3>
          <p className="mt-2 text-sm">{text}</p>
        </Link>
      ))}
    </div>
    <Card>
      <CardContent className="flex flex-wrap justify-between gap-2 p-6 text-sm">
        <span>Version: {health.data?.version ?? 'Not available'}</span>
        <span>Last updated: {health.dataUpdatedAt ? new Date(health.dataUpdatedAt).toLocaleString() : 'Waiting for backend'}</span>
      </CardContent>
    </Card>
  </div>
}
