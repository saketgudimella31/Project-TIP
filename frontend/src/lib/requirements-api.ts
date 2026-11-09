import axios from 'axios'

// Keep the existing API client and endpoints unchanged.
const requirementsClient = axios.create({ baseURL: '/api/v1', timeout: 30_000 })

export interface ManualStory {
  id: string
  title: string
  description: string
  acceptanceCriteria: string
  priority: string | null
}

export interface AnalysisOptions {
  target_application: string
  analysis_mode: 'FULL' | 'INCREMENTAL' | 'UNKNOWN'
  code_source: 'uploads' | 'repository' | 'local' | 'indexed'
  upload_kind: 'LOCAL_FILES' | 'LOCAL_FOLDER' | 'ARCHIVE'
  repo_url?: string
  local_path?: string
  branch?: string
  selected_path?: string
  indexed_repo_id?: string
  focus?: string
  jira_issue_keys: string[]
  manual_stories: ManualStory[]
}

export interface Evidence {
  sourceType: 'CODE' | 'DESIGN_DOCUMENT' | 'JIRA_USER_STORY' | 'RAW_REQUIREMENT'
  sourceName: string
  filePath: string | null
  externalId: string | null
  worksheet: string | null
  row: number | null
  lineStart: number | null
  lineEnd: number | null
  evidenceDescription: string
}

export interface Requirement {
  id: string
  requirement: string
  acceptanceCriterion: string
  priority: string | number | null
  requirementOrigin: string[]
  sourceEvidence: Evidence[]
  implementationEvidenceStatus: string
  evidenceStatus: string
  validationNotes: string
}

export interface Analysis {
  status: 'SUCCESS'
  schemaVersion: '2.0'
  documentTitle: string
  executiveSummary: string
  highLevelRequirements: Requirement[]
  nonFunctionalRequirements: Requirement[]
  evidenceConflicts: unknown[]
  limitations: string[]
  warnings: string[]
  validationStatement: string
}

export interface AnalysisTask {
  task_id: string
  status: 'pending' | 'running' | 'success' | 'failed' | 'cancelled'
  progress: number
  message: string
  created_at: string
  error?: string
  metadata?: { kind?: string; target_application?: string }
  result?: {
    analysis?: Analysis
    files_processed?: number
    repo_id?: string
    duration_ms?: number
  }
}

export interface Configuration {
  gateway_configured: boolean
  gateway_auth_configured: boolean
  rag_configured: boolean
  persistence_configured: boolean
  persistence_backend: string
  jira_configured: boolean
  server_directories_enabled: boolean
  max_upload_bytes: number
  max_files: number
}

export interface Uploads {
  code_files: File[]
  design_files: File[]
  requirements_files: File[]
  story_files: File[]
}

export function errorMessage(error: unknown): string {
  if (axios.isAxiosError<{ detail?: unknown }>(error)) {
    const detail = error.response?.data?.detail
    return typeof detail === 'string'
      ? detail
      : detail ? JSON.stringify(detail) : error.message
  }
  return error instanceof Error ? error.message : 'Unexpected request failure'
}

export const requirementsApi = {
  configuration: () => requirementsClient.get<Configuration>('/configuration'),
  submit: (options: AnalysisOptions, uploads: Uploads) => {
    const form = new FormData()
    form.append('options', JSON.stringify(options))
    for (const [field, files] of Object.entries(uploads)) {
      for (const file of files) {
        form.append(field, file, file.webkitRelativePath || file.name)
      }
    }
    return requirementsClient.post<{ task_id: string }>('/analysis', form)
  },
  task: (taskId: string) => requirementsClient.get<AnalysisTask>(`/tasks/${taskId}`),
  tasks: () => requirementsClient.get<{ tasks: AnalysisTask[] }>('/tasks', { params: { limit: 100 } }),
  cancel: (taskId: string) => requirementsClient.post(`/tasks/${taskId}/cancel`),
  documentUrl: (taskId: string) => `/api/v1/tasks/${taskId}/document`,
  analysisUrl: (taskId: string) => `/api/v1/tasks/${taskId}/analysis`,
}