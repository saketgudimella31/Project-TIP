import { useQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { Activity, Clock, Database, TrendingUp } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { errorMessage } from '../lib/requirements-api'
import { metricTotal, parseMetrics, platformApi, serviceState } from '../lib/platform-api'

export const Route = createFileRoute('/metrics')({ component: Metrics })

function Metrics() {
  const metrics = useQuery({
    queryKey: ['metrics'],
    queryFn: platformApi.metrics,
    refetchInterval: 10000,
  })
  const health = useQuery({
    queryKey: ['health'], queryFn: platformApi.health, refetchInterval: 10000,
  })
  const samples = parseMetrics(metrics.data ?? '')
  const sqlite = serviceState(health.data, ['sqlite_connected'])
  const total = (names: string[]) => metricTotal(samples, names)?.toLocaleString() ?? 'Not reported'
  return <div className="space-y-6">
    <header><h2 className="text-3xl font-bold">Metrics</h2><p>System performance and statistics</p></header>
    {metrics.isError && <p role="alert">{errorMessage(metrics.error)}</p>}
    {health.isError && <p role="alert">{errorMessage(health.error)}</p>}
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {[
        { label: 'SQLite Status', icon: Database, value: sqlite === undefined ? 'Not reported' : sqlite ? 'Connected' : 'Unavailable',
          description: 'Analysis and source storage', color: sqlite === false ? 'text-red-600' : sqlite ? 'text-green-600' : '' },
        { label: 'Total Requests', icon: Activity, value: total(['http_requests_total', 'http_server_requests_total']),
          description: 'HTTP requests processed', color: '' },
        { label: 'Repositories', icon: TrendingUp, value: total(['repositories_ingested_total', 'ingestion_total']),
          description: 'Total ingestions', color: '' },
        { label: 'Files Ingested', icon: Clock, value: total(['tip_indexed_files', 'files_ingested_total']),
          description: 'Code files processed', color: '' },
        { label: 'Saved Analyses', icon: Database, value: total(['tip_saved_analyses']),
          description: 'Analysis results stored in SQLite', color: '' },
      ].map(({ label, icon: Icon, value, description, color }) => (
        <Card key={label}><CardContent className="p-6">
          <div className="flex justify-between gap-2"><span className="text-sm">{label}</span><Icon className="h-4 w-4" /></div>
          <p className={`mt-3 text-2xl font-semibold ${color}`}>{value}</p>
          <p className="mt-1 text-xs">{description}</p>
        </CardContent></Card>
      ))}
    </div>
    <Card>
      <CardHeader><CardTitle>Graph Operations</CardTitle><p className="text-sm">Query and analysis statistics</p></CardHeader>
      <CardContent className="flex items-center justify-between gap-3">
        <span className="text-sm">Total Graph Queries</span>
        <span className="text-2xl font-semibold">{total(['graph_queries_total'])}</span>
      </CardContent>
    </Card>
    <Card>
      <CardHeader><CardTitle>SQLite Persistence</CardTitle><p className="text-sm">Normalized saved analysis and evidence records</p></CardHeader>
      <CardContent className="grid gap-4 md:grid-cols-2 text-sm">
        <div><h3 className="font-medium">Saved Analyses</h3><p className="mt-2">{total(['tip_saved_analyses'])}</p></div>
        <div><h3 className="font-medium">Saved Requirements</h3><p className="mt-2">{total(['tip_saved_requirements'])}</p></div>
      </CardContent>
    </Card>
    <Card>
      <CardHeader><CardTitle>Raw Metrics</CardTitle><p className="text-sm">Prometheus format metrics</p></CardHeader>
      <CardContent>
        <pre className="min-h-10 overflow-auto text-sm">{metrics.isPending ? 'Loading metrics...' : metrics.data}</pre>
      </CardContent>
    </Card>
  </div>
}