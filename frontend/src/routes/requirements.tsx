import { useState, type FormEvent } from 'react'
import { createFileRoute, Navigate } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Code2, FileArchive, FileText, Files, FolderOpen, Sheet, Trash2 } from 'lucide-react'
import { FileUpload } from '../components/file-upload'
import { DocumentDownload } from '../components/document-download'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'
import { Select } from '../components/ui/select'
import {
  requirementsApi, errorMessage, type AnalysisOptions,
  type Requirement, type Uploads,
} from '../lib/requirements-api'

export const Route = createFileRoute('/requirements')({
  validateSearch: (search: Record<string, unknown>): { task?: string } => ({
    task: typeof search.task === 'string' ? search.task : undefined,
  }),
  component: RequirementsRedirect,
})

const initialOptions: AnalysisOptions = {
  target_application: '',
  analysis_mode: 'INCREMENTAL',
  code_source: 'uploads',
  upload_kind: 'LOCAL_FILES',
  jira_issue_keys: [],
}

function RequirementList({ title, items }: { title: string; items: Requirement[] }) {
  return (
    <section className="space-y-3">
      <h3 className="text-lg font-semibold">{title}</h3>
      {items.length === 0 && <p>Not evidenced in the supplied artifacts.</p>}
      {items.map((item) => (
        <article className="rounded border p-4 space-y-2" key={item.id}>
          <h4 className="font-semibold">{item.id}: {item.requirement}</h4>
          <p>Acceptance criterion: {item.acceptanceCriterion || 'Not supplied'}</p>
          {item.childRequirements && item.childRequirements.length > 0 && (
            <ul className="ml-5 list-disc">
              {item.childRequirements.map((child, index) => (
                <li key={`${child.name}-${index}`}>
                  <strong>{child.name}:</strong> {child.requirement}
                </li>
              ))}
            </ul>
          )}
          <p className="text-sm">
            {item.evidenceStatus} / {item.implementationEvidenceStatus}
            {' / '}Priority: {item.priority ?? 'Not supplied'}
          </p>
          {item.validationNotes && <p>{item.validationNotes}</p>}
          <details>
            <summary className="cursor-pointer">Source evidence</summary>
            {item.sourceEvidence.map((evidence, index) => (
              <p className="mt-2 text-sm" key={index}>
                <strong>{evidence.sourceType}</strong>: {evidence.filePath || evidence.sourceName}
                {evidence.externalId && ` / ${evidence.externalId}`}
                {evidence.worksheet && ` / ${evidence.worksheet}`}
                {evidence.row && ` / row ${evidence.row}`}
                {evidence.lineStart && ` / lines ${evidence.lineStart}-${evidence.lineEnd ?? evidence.lineStart}`}
                {' - '}{evidence.evidenceDescription}
              </p>
            ))}
          </details>
        </article>
      ))}
    </section>
  )
}

function RequirementsRedirect() {
  const { task } = Route.useSearch()
  return <Navigate
    to="/repositories"
    search={{ task }}
    replace
  />
}

export function RequirementsPanel({
  taskId,
  onTaskChange,
}: {
  taskId?: string
  onTaskChange: (taskId: string | undefined) => void
}) {
  const selectedTask = taskId
  const queryClient = useQueryClient()
  const [options, setOptions] = useState(initialOptions)
  const [uploads, setUploads] = useState<Uploads>({
    code_files: [], design_files: [], requirements_files: [], story_files: [],
  })
  const [jiraKeys, setJiraKeys] = useState('')
  const [validationError, setValidationError] = useState('')
  const [historyMessage, setHistoryMessage] = useState('')
  const [automaticDownload, setAutomaticDownload] = useState(true)
  const [downloadTaskId, setDownloadTaskId] = useState<string>()
  const config = useQuery({
    queryKey: ['requirements-configuration'],
    queryFn: async () => (await requirementsApi.configuration()).data,
  })
  const task = useQuery({
    queryKey: ['requirements-task', selectedTask],
    queryFn: async () => (await requirementsApi.task(selectedTask!)).data,
    enabled: Boolean(selectedTask),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'pending' || status === 'running' ? 1000 : false
    },
  })
  const history = useQuery({
    queryKey: ['requirements-history'],
    queryFn: async () => (await requirementsApi.tasks()).data.tasks,
    refetchInterval: 5000,
  })
  const submit = useMutation({
    mutationFn: (payload: { options: AnalysisOptions; uploads: Uploads }) =>
      requirementsApi.submit(payload.options, payload.uploads),
    onSuccess: async ({ data }) => {
      setDownloadTaskId(automaticDownload ? data.task_id : undefined)
      onTaskChange(data.task_id)
      await queryClient.invalidateQueries({ queryKey: ['requirements-history'] })
    },
  })
  const cancel = useMutation({
    mutationFn: () => requirementsApi.cancel(selectedTask!),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['requirements-task', selectedTask] })
      await queryClient.invalidateQueries({ queryKey: ['requirements-history'] })
    },
  })
  const clearHistory = useMutation({
    mutationFn: requirementsApi.clearAnalysisHistory,
    onSuccess: async ({ data }) => {
      if (selectedTask && data.deleted_task_ids.includes(selectedTask)) {
        onTaskChange(undefined)
      }
      setHistoryMessage(
        `Cleared ${data.deleted_count} saved ${data.deleted_count === 1 ? 'analysis' : 'analyses'}. `
        + `${data.active_count} active ${data.active_count === 1 ? 'analysis was' : 'analyses were'} kept. `
        + 'Indexed repositories were not changed.',
      )
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['requirements-history'] }),
        queryClient.invalidateQueries({ queryKey: ['requirements-task'] }),
      ])
    },
  })
  const running = task.data?.status === 'pending' || task.data?.status === 'running'
  const codeSource = options.code_source
  const needsDiagramRenderer = codeSource !== 'uploads' || uploads.code_files.length > 0
  const diagramRendererMissing = config.data?.diagram_renderer_configured === false
  const setCodeSource = (value: AnalysisOptions['code_source']) => {
    setOptions((current) => ({
      ...current, code_source: value, selected_path: undefined, focus: undefined,
      repo_url: undefined, branch: undefined, local_path: undefined, indexed_repo_id: undefined,
    }))
    setUploads((current) => ({ ...current, code_files: [] }))
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setValidationError('')
    submit.reset()
    cancel.reset()
    const keys = jiraKeys.split(/[\s,;]+/).filter(Boolean)
    if (keys.some((key) => !/^[A-Za-z][A-Za-z0-9_]*-\d+$/.test(key))) {
      setValidationError('Use Jira issue keys such as TIP-123, separated by commas or spaces.')
      return
    }
    if (options.selected_path && options.analysis_mode === 'FULL') {
      setValidationError('Selected paths require INCREMENTAL or UNKNOWN scope.')
      return
    }
    if (codeSource === 'uploads' && !Object.values(uploads).some((files) => files.length) && !keys.length) {
      setValidationError('Provide source code, supporting evidence, or both.')
      return
    }
    if (needsDiagramRenderer && diagramRendererMissing) {
      setValidationError(
        config.data?.diagram_renderer_issue
          ?? 'Install Node.js 22.12+ and the Mermaid dependencies in frontend, then restart TIP.',
      )
      return
    }
    if (config.data) {
      const files = Object.values(uploads).flat()
      if (files.length > config.data.max_files || files.reduce((total, file) => total + file.size, 0) > config.data.max_upload_bytes) {
        setValidationError('The selected files exceed the backend file-count or combined-size limit.')
        return
      }
    }
    submit.mutate({
      options: { ...options, jira_issue_keys: keys },
      uploads,
    })
  }

  const result = task.data?.result?.analysis
  const canonical = task.data?.result?.canonical
  const analysisHistory = history.data?.filter((item) => item.metadata?.kind === 'analysis') ?? []
  function clearPreviousAnalyses() {
    if (!analysisHistory.length || clearHistory.isPending) return
    const confirmed = window.confirm(
      'Clear saved analysis history and its generated outputs? Indexed repository data will be kept.',
    )
    if (!confirmed) return
    setHistoryMessage('')
    clearHistory.mutate()
  }
  return (
    <div className="mx-auto w-full max-w-7xl space-y-6">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold flex items-center gap-2"><FileText />Generate requirements</h1>
        <p className="max-w-3xl text-muted-foreground">
          Provide source code, supporting evidence, or both. At least one input is required.
        </p>
      </header>
      {config.isError && <p role="alert">Backend configuration unavailable: {errorMessage(config.error)}</p>}
      {config.data?.analysis_prompts_configured === false && (
        <p role="alert" className="rounded border border-amber-500 p-3">
          {config.data.analysis_prompt_issue ?? 'The backend analysis prompt is missing or unreadable.'}
        </p>
      )}
      {diagramRendererMissing && (
        <p role="alert" className="rounded border border-amber-500 p-3">
          Code-based analysis requires embedded UML images; TIP will not publish text-only UML reports.
          {' '}{config.data?.diagram_renderer_issue
            ?? 'Install Node.js 22.12+ and the Mermaid dependencies in frontend, then restart TIP.'}
        </p>
      )}
      {config.data && !config.data.gateway_configured && (
        <p role="alert" className="rounded border border-amber-500 p-3">
          The backend AI gateway endpoint is not configured. Set TIP_GATEWAY_URL to the complete completion endpoint.
        </p>
      )}
      {config.data?.gateway_configured && !config.data.gateway_auth_configured && (
        <p role="alert" className="rounded border border-amber-500 p-3">
          Gateway authentication is incomplete. Set TIP_GATEWAY_APP_CONSUMER_KEY and TIP_GATEWAY_HMAC_SECRET on the backend. The supplied Postman signature formula is configured by default.
        </p>
      )}
      {config.data && !config.data.persistence_configured && (
        <p role="alert" className="rounded border border-amber-500 p-3">
          SQLite result storage is unavailable. Check that the backend data directory is writable.
        </p>
      )}
      <form onSubmit={onSubmit}>
        <fieldset disabled={submit.isPending || running} className="space-y-4 disabled:opacity-70">
          <Card>
            <CardHeader className="p-4 pb-3"><CardTitle>Application and analysis scope</CardTitle></CardHeader>
            <CardContent className="grid gap-4 px-4 pb-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="application">Target application</Label>
                <Input id="application" required maxLength={200} value={options.target_application}
                  onChange={(e) => setOptions({ ...options, target_application: e.target.value })} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="analysis-mode">Scope</Label>
                <Select id="analysis-mode" value={options.analysis_mode}
                  onChange={(e) => setOptions({ ...options, analysis_mode: e.target.value as AnalysisOptions['analysis_mode'] })}>
                  <option value="INCREMENTAL">Incremental: selected artifacts only</option>
                  <option value="FULL">Full: I am supplying the complete selected scope (within model limits)</option>
                  <option value="UNKNOWN">Unknown completeness</option>
                </Select>
              </div>
            </CardContent>
          </Card>
          <div className="grid items-start gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader className="p-4 pb-3"><CardTitle>Source code</CardTitle></CardHeader>
            <CardContent className="space-y-3 px-4 pb-4">
              <Label htmlFor="code-source">Source</Label>
              <Select id="code-source" value={codeSource}
                onChange={(e) => setCodeSource(e.target.value as AnalysisOptions['code_source'])}>
                <option value="uploads">Upload files, folder, or ZIP</option>
                <option value="repository">GitHub / GitLab / Bitbucket repository</option>
                {config.data?.server_directories_enabled && <option value="local">Allowed server directory</option>}
              </Select>
              {codeSource === 'uploads' && <>
                <div className="grid gap-3 sm:grid-cols-3" role="group" aria-label="Upload type">
                  {([
                    { value: 'LOCAL_FILES', label: 'Files', icon: Files },
                    { value: 'LOCAL_FOLDER', label: 'Folder', icon: FolderOpen },
                    { value: 'ARCHIVE', label: 'ZIP archive', icon: FileArchive },
                  ] as const).map(({ value, label, icon: Icon }) => (
                    <Button key={value} type="button" variant="outline"
                      aria-pressed={options.upload_kind === value}
                      className={`gap-2 border-2 ${options.upload_kind === value
                        ? 'border-primary bg-primary/5 text-primary hover:bg-primary/10'
                        : 'border-input text-foreground hover:bg-accent'}`}
                      onClick={() => {
                        if (options.upload_kind !== value) {
                          setOptions({ ...options, upload_kind: value })
                          setUploads({ ...uploads, code_files: [] })
                        }
                      }}>
                      <Icon className="h-5 w-5" aria-hidden="true" />{label}
                    </Button>
                  ))}
                </div>
                <FileUpload key={options.upload_kind} id="code-files"
                  compact
                  title={options.upload_kind === 'LOCAL_FOLDER' ? 'Code folder' : options.upload_kind === 'ARCHIVE' ? 'Code archive' : 'Code files'}
                  action={options.upload_kind === 'LOCAL_FOLDER' ? 'Upload folder' : options.upload_kind === 'ARCHIVE' ? 'Upload ZIP' : 'Upload code'}
                  icon={options.upload_kind === 'LOCAL_FOLDER' ? FolderOpen : options.upload_kind === 'ARCHIVE' ? FileArchive : Code2}
                  accept={options.upload_kind === 'ARCHIVE' ? '.zip' : undefined}
                  folder={options.upload_kind === 'LOCAL_FOLDER'}
                  files={uploads.code_files}
                  onChange={(files) => setUploads({ ...uploads, code_files: files })} />
              </>}
              {codeSource === 'repository' && <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2 md:col-span-2">
                  <Label htmlFor="repo-url">Authorized HTTPS repository URL</Label>
                  <Input id="repo-url" type="url" required placeholder="https://github.com/owner/repository.git"
                    value={options.repo_url ?? ''} onChange={(e) => setOptions({ ...options, repo_url: e.target.value })} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="branch">Branch (optional)</Label>
                  <Input id="branch" value={options.branch ?? ''} onChange={(e) => setOptions({ ...options, branch: e.target.value || undefined })} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="selected-path">Selected subdirectory (optional)</Label>
                  <Input id="selected-path" placeholder="e.g. src/application"
                    value={options.selected_path ?? ''} onChange={(e) => setOptions({ ...options, selected_path: e.target.value || undefined })} />
                </div>
                <div className="space-y-2 md:col-span-2">
                  <Label htmlFor="analysis-focus">Analysis focus (recommended for large repositories)</Label>
                  <Input id="analysis-focus" maxLength={2000}
                    placeholder="e.g. order status, authentication, payment flows"
                    value={options.focus ?? ''}
                    onChange={(e) => setOptions({ ...options, focus: e.target.value || undefined })} />
                </div>
              </div>}
              {codeSource === 'local' && <div className="space-y-2">
                <Label htmlFor="local-path">Server path inside the configured allowed root</Label>
                <Input id="local-path" required value={options.local_path ?? ''}
                  onChange={(e) => setOptions({ ...options, local_path: e.target.value })} />
                <Label htmlFor="local-analysis-focus">Analysis focus (recommended for large directories)</Label>
                <Input id="local-analysis-focus" maxLength={2000}
                  placeholder="e.g. order status, authentication, payment flows"
                  value={options.focus ?? ''}
                  onChange={(e) => setOptions({ ...options, focus: e.target.value || undefined })} />
              </div>}
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="p-4 pb-3"><CardTitle>Supporting evidence</CardTitle></CardHeader>
            <CardContent className="space-y-3 px-4 pb-4">
              <div className="grid gap-2">
                <FileUpload id="design-files" title="Design documents" action="Upload designs"
                  compact
                  formats="DOCX, PDF, TXT, MD" accept=".docx,.pdf,.txt,.md" icon={FileText}
                  files={uploads.design_files}
                  onChange={(files) => setUploads({ ...uploads, design_files: files })} />
                <FileUpload id="requirements-files" title="Requirements" action="Upload Excel"
                  compact
                  formats="XLSX, XLS" accept=".xlsx,.xls" icon={Sheet}
                  files={uploads.requirements_files}
                  onChange={(files) => setUploads({ ...uploads, requirements_files: files })} />
                <FileUpload id="story-files" title="Jira/story evidence" action="Upload evidence"
                  compact
                  formats="JSON, TXT, MD" accept=".json,.txt,.md" icon={Files}
                  files={uploads.story_files}
                  onChange={(files) => setUploads({ ...uploads, story_files: files })} />
              </div>
              {config.data?.jira_configured && <div className="space-y-2">
                <Label htmlFor="jira-keys">Jira story keys (optional)</Label>
                <Input id="jira-keys" placeholder="TIP-123, TIP-456" value={jiraKeys}
                  onChange={(e) => setJiraKeys(e.target.value)} />
              </div>}
            </CardContent>
          </Card>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={automaticDownload}
              onChange={(event) => setAutomaticDownload(event.target.checked)} />
            Automatically download the final requirements DOCX when analysis finishes
          </label>
          <Button type="submit" className="shadow-sm"
            disabled={!config.data?.gateway_configured || !config.data?.gateway_auth_configured
              || !config.data?.persistence_configured || config.data?.analysis_prompts_configured === false
              || (needsDiagramRenderer && diagramRendererMissing)}>
            {submit.isPending ? 'Uploading...' : 'Generate requirements'}
          </Button>
          </div>
        </fieldset>
      </form>
      {(validationError || submit.isError || cancel.isError) && (
        <p role="alert" className="text-red-700">{validationError || errorMessage(submit.error || cancel.error)}</p>
      )}
      {task.isError && <p role="alert">{errorMessage(task.error)}</p>}
      {task.data && <Card>
        <CardHeader><CardTitle>Analysis task</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <p>{task.data.status}: {task.data.message}</p>
          <p className="break-all text-sm">Task ID: {task.data.task_id}</p>
          {task.data.result?.repository_coverage && (
            <p role="note" className="text-sm">
              Analyzed {task.data.result.repository_coverage.retrievedCodeFiles.toLocaleString()} of
              {' '}{task.data.result.repository_coverage.indexedCodeFiles.toLocaleString()} eligible readable code files
              {' '}across {task.data.result.repository_coverage.analysisBatchCount.toLocaleString()} bounded model batches.
            </p>
          )}
          <progress aria-label="Analysis progress" className="w-full" max={100} value={task.data.progress} />
          {task.data.error && <p role="alert" className="text-red-700">{task.data.error}</p>}
          {running && <Button variant="outline" disabled={cancel.isPending} onClick={() => cancel.mutate()}>Cancel analysis</Button>}
          {task.data.status === 'success' && canonical && (
            <div className="grid gap-2 rounded border p-3 text-sm sm:grid-cols-2">
              <p>Analysis mode: {canonical.project.analysisMode}</p>
              <p>Parent requirements: {canonical.analysisSummary.parentRequirements}</p>
              <p>Child requirements: {canonical.analysisSummary.childRequirements}</p>
              <p>Implementation verified: {canonical.project.implementationVerified}</p>
            </div>
          )}
          {task.data.status === 'success' && result && <DocumentDownload taskId={task.data.task_id}
            automatically={downloadTaskId === task.data.task_id}
            projectName={canonical?.project.projectName ?? 'Project'} />}
        </CardContent>
      </Card>}
      {result && <Card>
        <CardHeader><CardTitle>{result.documentTitle}</CardTitle></CardHeader>
        <CardContent className="space-y-6">
          <p>{result.executiveSummary}</p>
          {result.warnings.length > 0 && <section>
            <h3 className="font-semibold">Warnings and scope limitations</h3>
            {result.warnings.map((warning, index) => <p role="note" key={index}>{warning}</p>)}
          </section>}
          <RequirementList title="Functional requirements" items={result.highLevelRequirements} />
          <RequirementList title="Non-functional requirements" items={result.nonFunctionalRequirements} />
          {result.evidenceConflicts.length > 0 && <section>
            <h3 className="font-semibold">Evidence conflicts requiring review</h3>
            {result.evidenceConflicts.map((conflict, index) => (
              <pre className="whitespace-pre-wrap break-words text-sm" key={index}>{JSON.stringify(conflict, null, 2)}</pre>
            ))}
          </section>}
          <p className="font-medium">{result.validationStatement}</p>
        </CardContent>
      </Card>}
      <Card>
        <CardHeader className="flex-row flex-wrap items-center justify-between gap-4 space-y-0">
          <div className="space-y-1">
            <CardTitle>Previous analyses</CardTitle>
            <p className="text-sm text-muted-foreground">
              Clear saved analyses and their outputs without removing indexed repositories.
            </p>
          </div>
          <Button type="button" variant="outline"
            className="border-brand-orange text-brand-orange hover:bg-orange-50"
            disabled={!analysisHistory.length || history.isPending || clearHistory.isPending}
            onClick={clearPreviousAnalyses}>
            <Trash2 className="mr-2 h-4 w-4" aria-hidden="true" />
            {clearHistory.isPending ? 'Clearing…' : 'Clear analysis history'}
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          {history.isError && <p role="alert">{errorMessage(history.error)}</p>}
          {clearHistory.isError && <p role="alert">{errorMessage(clearHistory.error)}</p>}
          {historyMessage && <p role="status">{historyMessage}</p>}
          {history.data && analysisHistory.length === 0 && (
            <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
              No previous analyses.
            </p>
          )}
          {analysisHistory.map((item) => (
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b py-3 last:border-b-0"
              key={item.task_id}>
              <Button variant="link" onClick={() => onTaskChange(item.task_id)}>
                {item.metadata?.target_application || item.task_id}
              </Button>
              <span className="rounded-full bg-secondary px-2.5 py-1 text-xs font-medium text-secondary-foreground">
                {item.status}
              </span>
              <time className="text-sm text-muted-foreground">{new Date(item.created_at).toLocaleString()}</time>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
