import { useQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'
import { Clock, Database } from 'lucide-react'
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
  const graphQueries = (status: 'success' | 'error') => {
    const values = samples.filter((sample) =>
      sample.name === 'graph_queries_total'
      && new RegExp(`(?:\\{|,)status="${status}"(?:,|\\})`).test(sample.labels))
    return values.length
      ? values.reduce((sum, sample) => sum + sample.value, 0).toLocaleString()
      : 'Not reported'
  }
  return <div className="space-y-6">
    <header><h2 className="text-3xl font-bold">Metrics</h2><p>System performance and statistics</p></header>
    {metrics.isError && <p role="alert">{errorMessage(metrics.error)}</p>}
    {health.isError && <p role="alert">{errorMessage(health.error)}</p>}
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {[
        { label: 'SQLite Status', icon: Database, value: sqlite === undefined ? 'Not reported' : sqlite ? 'Connected' : 'Unavailable',
          description: 'Analysis and source storage', color: sqlite === false ? 'text-red-600' : sqlite ? 'text-green-600' : '' },
        { label: 'Files Ingested', icon: Clock, value: total(['tip_indexed_files', 'files_ingested_total']),
          description: 'Code files currently indexed', color: '' },
        { label: 'Saved Analyses', icon: Database, value: total(['tip_saved_analyses']),
          description: 'Analysis results stored in SQLite', color: '' },
        { label: 'Saved Requirements', icon: Database, value: total(['tip_saved_requirements']),
          description: 'Requirement records stored in SQLite', color: '' },
      ].map(({ label, icon: Icon, value, description, color }) => (
        <Card key={label}><CardContent className="p-6">
          <div className="flex justify-between gap-2"><span className="text-sm">{label}</span><Icon className="h-4 w-4" /></div>
          <p className={`mt-3 text-2xl font-semibold ${color}`}>{value}</p>
          <p className="mt-1 text-xs">{description}</p>
        </CardContent></Card>
      ))}
    </div>
    <Card>
      <CardHeader><CardTitle>Graph Operations</CardTitle><p className="text-sm">
        Dependency, symbol, and cross-file relationship lookups recorded by the backend
      </p></CardHeader>
      <CardContent className="grid gap-4 sm:grid-cols-3">
        <div>
          <p className="text-sm">Total graph queries</p>
          <p className="text-2xl font-semibold">{total(['graph_queries_total'])}</p>
        </div>
        <div>
          <p className="text-sm">Successful</p>
          <p className="text-2xl font-semibold">{graphQueries('success')}</p>
        </div>
        <div>
          <p className="text-sm">Failed</p>
          <p className="text-2xl font-semibold">{graphQueries('error')}</p>
        </div>
      </CardContent>
    </Card>
    <details className="rounded border p-4">
      <summary className="cursor-pointer font-medium">Raw metrics (Prometheus)</summary>
      <pre className="mt-4 min-h-10 overflow-auto text-sm">{metrics.isPending ? 'Loading metrics...' : metrics.data}</pre>
    </details>
  </div>
}