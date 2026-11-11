import axios from 'axios'
import type { AnalysisTask } from './requirements-api'

const client = axios.create({ baseURL: '/api/v1', timeout: 30_000 })

export interface Health {
  status: string
  services: Record<string, boolean>
  version: string
  graph_backend: 'kuzu' | 'sqlite'
  retrieval_backend: string
}

export interface ContextPack {
  repo_id: string
  budget_used: number
  budget_limit: number
  items: { ref: string; summary: string; extra: { path: string } }[]
}

export interface ImpactResult {
  repo_id: string
  file: string
  backend?: string
  nodes: { path: string; depth: number; relationship: string }[]
  relationships?: { source: string; target: string; type: string; line: number }[]
  warnings?: string[]
  limitations?: string[]
  truncated?: boolean
}

export type SearchMode = 'keyword' | 'vector' | 'hybrid'

export interface SymbolResult {
  symbols: { id: string; path: string; name: string; kind: string; line: number; end_line: number }[]
  calls: { source: string; target: string; line: number; caller: string | null; callee: string }[]
  unresolved_calls: { path: string; line: number; name: string }[]
  warnings: string[]
}

export interface KnowledgeSearch {
  nodes: { id: string; ref: string; text: string; score: number }[]
  semantic: boolean
  embedding_provider: string
}

export interface ProjectMemory {
  id: string
  title: string
  content: string
  memory_type: 'decision' | 'preference' | 'experience' | 'convention' | 'plan' | 'note'
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
    selected_path?: string
    mode: 'full' | 'incremental'
  }) => (await client.post<{ task_id: string; repo_id?: string }>('/ingest/repo', data)).data,
  context: async (repoId: string, focus: string, mode: SearchMode = 'hybrid') => (
    await client.get<ContextPack>('/context/pack', { params: { repoId, focus, mode, budget: 12000 } })
  ).data,
  impact: async (repoId: string, file: string, depth: number) => (
    await client.get<ImpactResult>('/graph/impact', { params: { repoId, file, depth, limit: 50 } })
  ).data,
  symbols: async (repoId: string) => (
    await client.get<SymbolResult>('/graph/symbols', { params: { repoId } })
  ).data,
  search: async (scope: string, query: string, mode: SearchMode) => (
    await client.get<KnowledgeSearch>('/knowledge/search', { params: { scope, query, mode, top_k: 10 } })
  ).data,
  answer: async (scope: string, question: string, mode: SearchMode, session_id?: string) => (
    await client.post<{ answer: string; citations: string[]; session_id: string }>('/knowledge/query', {
      scope, question, mode, session_id,
    })
  ).data,
  memories: async (project_id: string) => (
    await client.get<{ memories: ProjectMemory[] }>('/memory/search', { params: { project_id } })
  ).data,
  addMemory: async (project_id: string, title: string, content: string, memory_type: ProjectMemory['memory_type']) => (
    await client.post('/memory/add', { project_id, title, content, memory_type })
  ).data,
  deleteMemory: async (id: string) => (await client.delete(`/memory/${id}`)).data,
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