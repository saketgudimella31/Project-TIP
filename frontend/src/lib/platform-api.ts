import axios from 'axios'
import type { AnalysisTask } from './requirements-api'

const client = axios.create({ baseURL: '/api/v1', timeout: 30_000 })

export interface Health {
  status: string
  services: Record<string, boolean>
  version: string
}

export const platformApi = {
  health: async () => (await client.get<Health>('/health')).data,
  metrics: async () => (await client.get<string>('/metrics', { responseType: 'text' })).data,
  tasks: async () => (await client.get<{ tasks: AnalysisTask[]; total_count: number }>(
    '/tasks', { params: { limit: 1000 } },
  )).data,
  ingest: async (data: {
    repo_url?: string
    local_path?: string
    branch?: string
    mode: 'full' | 'incremental'
  }) => (await client.post<{ task_id: string; repo_id?: string }>('/ingest/repo', data)).data,
}

export function serviceState(health: Health | undefined, names: string[]): boolean | undefined {
  if (!health) return undefined
  for (const name of names) {
    if (typeof health.services[name] === 'boolean') return health.services[name]
  }
  return undefined
}

export interface MetricSample {
  name: string
  labels: string
  value: number
}

export function parseMetrics(text: string): MetricSample[] {
  const result: MetricSample[] = []
  for (const line of text.split('\n')) {
    const match = line.match(/^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{[^}]*\})?\s+([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)(?:\s+\d+)?\s*$/)
    if (match) result.push({ name: match[1], labels: match[2] ?? '', value: Number(match[3]) })
  }
  return result
}

export function metricTotal(samples: MetricSample[], names: string[]): number | undefined {
  for (const name of names) {
    const found = samples.filter((sample) => sample.name === name)
    if (found.length) return found.reduce((sum, sample) => sum + sample.value, 0)
  }
  return undefined
}