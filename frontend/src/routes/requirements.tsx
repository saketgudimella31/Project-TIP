import { useState, type FormEvent } from 'react'
import { createFileRoute, Navigate } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Code2, FileArchive, FileText, Files, FolderOpen, Plus, Sheet, Trash2 } from 'lucide-react'
import { FileUpload } from '../components/file-upload'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'
import { Select } from '../components/ui/select'
import { Textarea } from '../components/ui/textarea'
import {
  requirementsApi, errorMessage, type AnalysisOptions, type ManualStory,
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
  manual_stories: [],
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
  onTaskChange: (taskId: string) => void
}) {
  const selectedTask = taskId
  const queryClient = useQueryClient()
  const [options, setOptions] = useState(initialOptions)
  const [uploads, setUploads] = useState<Uploads>({
    code_files: [], design_files: [], requirements_files: [], story_files: [],
  })
  const [jiraKeys, setJiraKeys] = useState('')
  const [stories, setStories] = useState<ManualStory[]>([])
  const [validationError, setValidationError] = useState('')
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
  const running = task.data?.status === 'pending' || task.data?.status === 'running'
  const updateStory = (index: number, patch: Partial<ManualStory>) =>
    setStories((current) => current.map((story, i) => i === index ? { ...story, ...patch } : story))
  const codeSource = options.code_source
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
    if (stories.some((story) => !story.id.trim() || !story.title.trim() || !story.description.trim())) {
      setValidationError('Each manual story needs an ID, title, and description.')
      return
    }
    if ((options.selected_path || options.focus) && options.analysis_mode === 'FULL') {
      setValidationError('Selected paths and retrieval focus require INCREMENTAL or UNKNOWN scope.')
      return
    }
    if (codeSource === 'uploads' && !Object.values(uploads).some((files) => files.length) && !keys.length && !stories.length) {
      setValidationError('Provide at least one source: code, Word design, Excel requirements, or stories.')
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
      options: { ...options, jira_issue_keys: keys, manual_stories: stories },
      uploads,
    })
  }

  const result = task.data?.result?.analysis
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-3xl font-bold flex items-center gap-2"><FileText />Requirements &amp; UML</h1>
        <p className="mt-2 text-muted-foreground">
          Add source artifacts to generate draft requirements and UML.
        </p>
      </header>
      {config.isError && <p role="alert">Backend configuration unavailable: {errorMessage(config.error)}</p>}
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
      {config.data && (
        <p role="status" className="text-sm">
          Indexed-source retrieval: {config.data.rag_configured ? 'optional external RAG file selector available' : 'built-in SQLite full-text search; no RAG model bundled'}
          {' · '}Result storage: {config.data.persistence_configured ? config.data.persistence_backend : 'Unavailable'}
        </p>
      )}
      <form className="space-y-6" onSubmit={onSubmit}>
        <fieldset disabled={submit.isPending || running} className="space-y-6 disabled:opacity-70">
          <Card>
            <CardHeader><CardTitle>Application and analysis scope</CardTitle></CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-2">
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
                  <option value="FULL">Full: I am supplying the complete selected application scope</option>
                  <option value="UNKNOWN">Unknown completeness</option>
                </Select>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Application code (optional)</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <Label htmlFor="code-source">Source</Label>
              <Select id="code-source" value={codeSource}
                onChange={(e) => setCodeSource(e.target.value as AnalysisOptions['code_source'])}>
                <option value="uploads">Upload files, folder, or ZIP</option>
                <option value="repository">GitHub / GitLab / Bitbucket repository</option>
                <option value="indexed">Previously indexed code (retrieve by focus)</option>
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
                      className={`h-14 gap-2 border-2 ${options.upload_kind === value
                        ? 'border-blue-700 bg-blue-50 text-blue-800 hover:bg-blue-100'
                        : 'border-slate-300 text-slate-700 hover:bg-slate-100'}`}
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
                  title={options.upload_kind === 'LOCAL_FOLDER' ? 'Code folder' : options.upload_kind === 'ARCHIVE' ? 'Code archive' : 'Code files'}
                  action={options.upload_kind === 'LOCAL_FOLDER' ? 'Upload folder' : options.upload_kind === 'ARCHIVE' ? 'Upload ZIP' : 'Upload code'}
                  icon={options.upload_kind === 'LOCAL_FOLDER' ? FolderOpen : options.upload_kind === 'ARCHIVE' ? FileArchive : Code2}
                  accept={options.upload_kind === 'ARCHIVE' ? '.zip' : undefined}
                  folder={options.upload_kind === 'LOCAL_FOLDER'}
                  files={uploads.code_files}
                  onChange={(files) => setUploads({ ...uploads, code_files: files })} />
                <p className="text-sm text-slate-600">
                  Uploaded code goes directly to analysis. Retrieval is used only when you select previously indexed code.
                </p>
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
                  <Input id="selected-path" value={options.selected_path ?? ''} onChange={(e) => setOptions({ ...options, selected_path: e.target.value || undefined })} />
                </div>
              </div>}
              {codeSource === 'local' && <div className="space-y-2">
                <Label htmlFor="local-path">Server path inside the configured allowed root</Label>
                <Input id="local-path" required value={options.local_path ?? ''}
                  onChange={(e) => setOptions({ ...options, local_path: e.target.value })} />
                <p className="text-sm">This is a backend server path, not a path on your browser's computer.</p>
              </div>}
              {codeSource === 'indexed' && <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-slate-800 md:col-span-2">
                  <h3 className="font-semibold text-blue-900">How retrieval works</h3>
                  <p className="mt-1">
                    This package has no separate RAG model or embeddings. With a focus, it searches the built-in SQLite text index
                    {config.data?.rag_configured ? ' or asks the configured RAG service to select source-file paths' : ''}.
                    It then loads the matching actual source files and sends those to the LLM. Leave focus blank to use the indexed source without external RAG selection.
                  </p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="repo-id">Indexed repository ID</Label>
                  <Input id="repo-id" required value={options.indexed_repo_id ?? ''}
                    onChange={(e) => setOptions({ ...options, indexed_repo_id: e.target.value })} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="focus">Retrieval focus (optional; partial scope)</Label>
                  <Input id="focus" value={options.focus ?? ''} onChange={(e) => setOptions({ ...options, focus: e.target.value })} />
                </div>
              </div>}
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Supporting evidence (optional)</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="grid items-start gap-4 lg:grid-cols-3">
                <FileUpload id="design-files" title="Design documents" action="Upload designs"
                  formats="DOCX, TXT, MD" accept=".docx,.txt,.md" icon={FileText}
                  files={uploads.design_files}
                  onChange={(files) => setUploads({ ...uploads, design_files: files })} />
                <FileUpload id="requirements-files" title="Requirements" action="Upload Excel"
                  formats="XLSX, XLS" accept=".xlsx,.xls" icon={Sheet}
                  files={uploads.requirements_files}
                  onChange={(files) => setUploads({ ...uploads, requirements_files: files })} />
                <FileUpload id="story-files" title="User stories" action="Upload stories"
                  formats="JSON, TXT, MD" accept=".json,.txt,.md" icon={Files}
                  files={uploads.story_files}
                  onChange={(files) => setUploads({ ...uploads, story_files: files })} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="jira-keys">Jira story keys (optional)</Label>
                <Input id="jira-keys" placeholder="TIP-123, TIP-456" value={jiraKeys}
                  disabled={!config.data?.jira_configured} onChange={(e) => setJiraKeys(e.target.value)} />
                {!config.data?.jira_configured && <p className="text-sm text-slate-600">Jira unavailable. Upload stories or add them below.</p>}
              </div>
              <details className="text-sm text-slate-600">
                <summary>Supported input details</summary>
                <p className="mt-2">Sensitive filenames and generated/dependency directories are excluded. Excel source locations remain traceable; formulas are not executed.</p>
                <p className="mt-2">Story JSON: an array with id, title, description, and optional acceptanceCriteria and priority.</p>
              </details>
              <h3 className="font-semibold">Manual user stories</h3>
              {stories.map((story, index) => (
                <div className="rounded border p-4 space-y-3" key={index}>
                  <div className="flex items-center justify-between">
                    <h4 className="font-medium">Story {index + 1}</h4>
                    <Button type="button" variant="ghost" aria-label={`Remove story ${index + 1}`}
                      onClick={() => setStories(stories.filter((_, i) => i !== index))}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                  <Label htmlFor={`story-${index}-id`}>Story ID</Label>
                  <Input id={`story-${index}-id`} required maxLength={100} value={story.id}
                    onChange={(e) => updateStory(index, { id: e.target.value })} />
                  <Label htmlFor={`story-${index}-title`}>Title</Label>
                  <Input id={`story-${index}-title`} required maxLength={500} value={story.title}
                    onChange={(e) => updateStory(index, { title: e.target.value })} />
                  <Label htmlFor={`story-${index}-description`}>User story / description</Label>
                  <Textarea id={`story-${index}-description`} required maxLength={20000} value={story.description}
                    onChange={(e) => updateStory(index, { description: e.target.value })} />
                  <Label htmlFor={`story-${index}-acceptance`}>Acceptance criteria (optional)</Label>
                  <Textarea id={`story-${index}-acceptance`} maxLength={20000} value={story.acceptanceCriteria}
                    onChange={(e) => updateStory(index, { acceptanceCriteria: e.target.value })} />
                  <Label htmlFor={`story-${index}-priority`}>Explicit priority (optional)</Label>
                  <Input id={`story-${index}-priority`} maxLength={100} value={story.priority ?? ''}
                    onChange={(e) => updateStory(index, { priority: e.target.value || null })} />
                </div>
              ))}
              <Button type="button" variant="outline" className="border-blue-700 text-blue-800 hover:bg-blue-50" disabled={stories.length >= 100}
                onClick={() => setStories([...stories, {
                  id: `US-${Date.now()}`, title: '', description: '', acceptanceCriteria: '', priority: null,
                }])}>
                <Plus className="mr-2 h-4 w-4" />Add user story
              </Button>
            </CardContent>
          </Card>
          <p className="text-sm">
            Supporting requirements do not prove implementation. Output is a draft requiring human review.
            Review uploads for secrets before submission.
          </p>
          <Button type="submit" className="bg-blue-700 text-white shadow-sm hover:bg-blue-800" disabled={!config.data?.gateway_configured || !config.data?.gateway_auth_configured || !config.data?.persistence_configured}>
            {submit.isPending ? 'Uploading...' : 'Generate requirements & Word document'}
          </Button>
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
          <progress aria-label="Analysis progress" className="w-full" max={100} value={task.data.progress} />
          {task.data.error && <p role="alert" className="text-red-700">{task.data.error}</p>}
          {running && <Button variant="outline" disabled={cancel.isPending} onClick={() => cancel.mutate()}>Cancel analysis</Button>}
          {task.data.status === 'success' && result && <div className="flex gap-4">
            <a className="underline" href={requirementsApi.documentUrl(task.data.task_id)}>Download Word document</a>
            <a className="underline" href={requirementsApi.analysisUrl(task.data.task_id)} target="_blank" rel="noreferrer">Structured analysis JSON</a>
          </div>}
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
        <CardHeader><CardTitle>Previous analyses</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {history.isError && <p role="alert">{errorMessage(history.error)}</p>}
          {history.data?.filter((item) => item.metadata?.kind === 'analysis').map((item) => (
            <div className="flex flex-wrap gap-3 items-center border-b py-2" key={item.task_id}>
              <Button variant="link" onClick={() => onTaskChange(item.task_id)}>
                {item.metadata?.target_application || item.task_id}
              </Button>
              <span>{item.status}</span><time>{new Date(item.created_at).toLocaleString()}</time>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
