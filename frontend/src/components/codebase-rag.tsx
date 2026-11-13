import { useState, type FormEvent } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { platformApi, type SearchMode } from '../lib/platform-api'
import { requirementsApi, errorMessage, type Configuration } from '../lib/requirements-api'
import { Button } from './ui/button'
import { Card, CardContent, CardHeader, CardTitle } from './ui/card'
import { Input } from './ui/input'
import { Label } from './ui/label'
import { Select } from './ui/select'
import { KnowledgePanel } from './knowledge-panel'

export function CodebaseRag({
  config, onSelectRepository,
}: {
  config?: Configuration
  onSelectRepository: (repoId: string) => void
}) {
  const [repoUrl, setRepoUrl] = useState('')
  const [branch, setBranch] = useState('')
  const [selectedPath, setSelectedPath] = useState('')
  const [repoId, setRepoId] = useState('')
  const [focus, setFocus] = useState('')
  const [file, setFile] = useState('')
  const [depth, setDepth] = useState(2)
  const [mode, setMode] = useState<SearchMode>('hybrid')
  const ingest = useMutation({
    mutationFn: () => platformApi.ingest({
      repo_url: repoUrl.trim(), branch: branch.trim() || undefined,
      selected_path: selectedPath.trim() || undefined, mode: 'full',
    }),
    onSuccess: (data) => {
      if (data.repo_id) setRepoId(data.repo_id)
    },
  })
  const task = useQuery({
    queryKey: ['ingestion-task', ingest.data?.task_id],
    queryFn: async () => (await requirementsApi.task(ingest.data!.task_id)).data,
    enabled: Boolean(ingest.data?.task_id),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return !status || status === 'pending' || status === 'running' ? 1000 : false
    },
  })
  const context = useMutation({
    mutationFn: () => platformApi.context(repoId.trim(), focus.trim(), mode),
  })
  const symbols = useMutation({ mutationFn: () => platformApi.symbols(repoId.trim()) })
  const impact = useMutation({
    mutationFn: () => platformApi.impact(repoId.trim(), file.trim(), depth),
  })
  const running = ingest.isPending || task.data?.status === 'pending' || task.data?.status === 'running'
  function submitIngest(event: FormEvent) {
    event.preventDefault()
    ingest.mutate()
  }
  return <Card>
    <CardHeader><CardTitle>Codebase RAG &amp; dependency graph</CardTitle></CardHeader>
    <CardContent className="space-y-5">
      {config && !config.graph_configured && <p role="alert">The code graph is unavailable. Check backend configuration.</p>}
      <form className="space-y-3" onSubmit={submitIngest}>
        <div className="grid gap-3 md:grid-cols-2">
          <div className="space-y-1">
            <Label htmlFor="rag-repo-url">Authorized HTTPS repository URL</Label>
            <Input id="rag-repo-url" type="url" required value={repoUrl}
              onChange={(event) => setRepoUrl(event.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="rag-branch">Branch (optional)</Label>
            <Input id="rag-branch" value={branch} onChange={(event) => setBranch(event.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="rag-selected-path">Selected subdirectory (optional)</Label>
            <Input id="rag-selected-path" placeholder="e.g. src/application" value={selectedPath}
              onChange={(event) => setSelectedPath(event.target.value)} />
          </div>
        </div>
        <Button type="submit" disabled={running}>Index repository</Button>
        <p className="text-sm text-slate-600">
          Private repositories require Git credentials configured on the backend; do not put credentials in the URL.
          Repositories are indexed in local batches up to {config?.max_repository_files?.toLocaleString() ?? '100,000'} readable files
          with a per-file size cap of {((config?.max_repository_file_bytes ?? 30000000) / 1_000_000).toLocaleString(undefined, { maximumFractionDigits: 1 })} MB.
          Larger indexes retain SQLite full-text search; graph and vector indexing may be skipped.
          Git clone/checkout operations time out after {config?.repository_clone_timeout_seconds?.toLocaleString() ?? '600'} seconds.
          A selected subdirectory uses sparse checkout; blob filtering depends on Git host support.
        </p>
      </form>
      {ingest.isError && <p role="alert">{errorMessage(ingest.error)}</p>}
      {task.isError && <p role="alert">{errorMessage(task.error)}</p>}
      {task.data && <p role="status">Indexing: {task.data.status} - {task.data.message}</p>}
      {task.data?.result?.files_indexed !== undefined && (
        <p role="note">{task.data.result.files_indexed.toLocaleString()} readable files indexed locally.</p>
      )}
      {task.data?.error && <p role="alert">{task.data.error}</p>}
      <div className="space-y-1">
        <Label htmlFor="rag-repo-id">Indexed repository ID</Label>
        <Input id="rag-repo-id" value={repoId} onChange={(event) => setRepoId(event.target.value)} />
      </div>
      <Button type="button" disabled={!repoId.trim() || running}
        onClick={() => onSelectRepository(repoId.trim())}>Use this repository for analysis</Button>
      <div>
        <Label htmlFor="rag-mode">Retrieval mode</Label>
        <Select id="rag-mode" value={mode} onChange={(event) => {
          const value = event.target.value
          if (value === 'keyword' || value === 'vector' || value === 'hybrid') setMode(value)
        }}>
          <option value="hybrid">Hybrid (keywords + vectors)</option>
          <option value="keyword">Keywords</option>
          <option value="vector">Vectors</option>
        </Select>
        <p className="text-sm">{config?.semantic_search
          ? 'Semantic sentence embeddings enabled'
          : 'Local token-hash vectors; configure the semantic provider for meaning-based search'}</p>
      </div>
      <form className="space-y-3" onSubmit={(event) => { event.preventDefault(); context.mutate() }}>
        <Label htmlFor="rag-focus">Source search (blank returns indexed files)</Label>
        <Input id="rag-focus" value={focus} onChange={(event) => setFocus(event.target.value)} />
        <Button type="submit" disabled={!repoId.trim() || context.isPending || running}>Retrieve source context</Button>
      </form>
      {context.isError && <p role="alert">{errorMessage(context.error)}</p>}
      {context.data && <section className="space-y-2" aria-label="Retrieved source context">
        <p>{context.data.items.length} files / {context.data.budget_used}/{context.data.budget_limit} characters / {context.data.repo_id}</p>
        {context.data.items.map((item) => <details key={item.ref}>
          <summary>{item.ref}</summary>
          <pre className="overflow-auto whitespace-pre-wrap rounded border p-3 text-xs">{item.summary}</pre>
        </details>)}
      </section>}
      <form className="space-y-3" onSubmit={(event) => { event.preventDefault(); impact.mutate() }}>
        <div className="grid gap-3 md:grid-cols-2">
          <div className="space-y-1">
            <Label htmlFor="rag-file">Changed file (repository-relative path)</Label>
            <Input id="rag-file" required value={file} onChange={(event) => setFile(event.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="rag-depth">Impact depth (1-5)</Label>
            <Input id="rag-depth" type="number" min={1} max={5} required value={depth}
              onChange={(event) => setDepth(Number(event.target.value))} />
          </div>
        </div>
        <Button type="submit" disabled={!repoId.trim() || impact.isPending || running}>Find dependent files</Button>
      </form>
      {impact.isError && <p role="alert">{errorMessage(impact.error)}</p>}
      {impact.data && <section className="space-y-2" aria-label="Dependency impact">
        <p>{impact.data.file} / {impact.data.backend ?? 'external RAG service'} / {impact.data.nodes.length} dependent files</p>
        {impact.data.nodes.length === 0 && <p>No statically resolved importers found within this depth.</p>}
        {impact.data.nodes.map((node) => <p key={node.path}>{node.path} - depth {node.depth}</p>)}
        {(impact.data.relationships ?? []).map((edge) => (
          <p className="text-sm" key={`${edge.source}:${edge.target}:${edge.type}:${edge.line}`}>
            {edge.source}:{edge.line} -&gt; {edge.target} ({edge.type})
          </p>
        ))}
        {impact.data.truncated && <p>Results limited to 50 files.</p>}
        {(impact.data.warnings ?? []).map((warning) => <p role="alert" key={warning}>{warning}</p>)}
      </section>}
      <Button type="button" disabled={!repoId.trim() || symbols.isPending}
        onClick={() => symbols.mutate()}>Show symbols and calls</Button>
      {symbols.isError && <p role="alert">{errorMessage(symbols.error)}</p>}
      {symbols.data && <details>
        <summary>{symbols.data.symbols.length} symbols / {symbols.data.calls.length} resolved calls / {symbols.data.unresolved_calls.length} unresolved calls</summary>
        {symbols.data.symbols.map((symbol) => <p key={symbol.id}>{symbol.path}:{symbol.line} {symbol.kind} {symbol.name}</p>)}
        {symbols.data.calls.map((call, index) => <p key={index}>{call.source}:{call.line} -&gt; {call.callee}</p>)}
        {symbols.data.warnings.map((warning) => <p role="alert" key={warning}>{warning}</p>)}
      </details>}
      <KnowledgePanel key={repoId.trim()} projectId={repoId.trim()} mode={mode} />
      <p className="text-sm">
        Static Python and JavaScript/TypeScript symbols, imports and resolved calls.
        Dynamic dispatch, external packages and module aliases may remain unresolved.
      </p>
    </CardContent>
  </Card>
}