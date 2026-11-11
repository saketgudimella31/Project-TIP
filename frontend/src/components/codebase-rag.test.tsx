import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AxiosHeaders } from 'axios'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { platformApi } from '../lib/platform-api'
import { requirementsApi, type Configuration } from '../lib/requirements-api'
import { CodebaseRag } from './codebase-rag'

vi.mock('../lib/platform-api', () => ({
  platformApi: {
    ingest: vi.fn(), context: vi.fn(), impact: vi.fn(), symbols: vi.fn(),
    search: vi.fn(), answer: vi.fn(), memories: vi.fn(), addMemory: vi.fn(), deleteMemory: vi.fn(),
  },
}))
vi.mock('../lib/requirements-api', () => ({
  requirementsApi: { task: vi.fn() },
  errorMessage: (error: Error) => error.message,
}))

const config: Configuration = {
  gateway_configured: true, gateway_auth_configured: true, rag_configured: false,
  persistence_configured: true, persistence_backend: 'SQLite',
  graph_backend: 'kuzu', graph_configured: true, retrieval_backend: 'SQLite FTS5',
  graph_limitations: [], jira_configured: false, server_directories_enabled: false,
  max_upload_bytes: 30000000, max_files: 500, max_artifact_characters: 150000,
  max_repository_files: 500000, max_repository_bytes: 5000000000,
  max_repository_file_bytes: 30000000,
  repository_clone_timeout_seconds: 600,
  max_analysis_files: 100, max_analysis_characters: 150000,
  analysis_batch_files: 5, analysis_batch_characters: 25000,
}

function setup() {
  const onSelectRepository = vi.fn()
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}>
    <CodebaseRag config={config} onSelectRepository={onSelectRepository} />
  </QueryClientProvider>)
  return { user: userEvent.setup(), onSelectRepository }
}

beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(platformApi.memories).mockResolvedValue({ memories: [] })
})

describe('Neo4j-free codebase RAG', () => {
  it('indexes a repository, polls its task, and selects it for existing analysis', async () => {
    vi.mocked(platformApi.ingest).mockResolvedValue({ task_id: 'ingest-1', repo_id: 'repo-1' })
    vi.mocked(requirementsApi.task).mockResolvedValue({
      data: { task_id: 'ingest-1', status: 'success', progress: 100, message: 'Completed', created_at: '' },
      status: 200, statusText: 'OK', headers: {}, config: { headers: new AxiosHeaders() },
    })
    const { user, onSelectRepository } = setup()
    await user.type(screen.getByLabelText('Authorized HTTPS repository URL'), 'https://github.com/example/project')
    await user.type(screen.getByLabelText('Branch (optional)'), 'develop')
    await user.type(screen.getByLabelText('Selected subdirectory (optional)'), 'src/application')
    await user.click(screen.getByRole('button', { name: 'Index repository' }))
    expect(await screen.findByText('Indexing: success - Completed')).toBeInTheDocument()
    expect(platformApi.ingest).toHaveBeenCalledWith({
      repo_url: 'https://github.com/example/project', branch: 'develop',
      selected_path: 'src/application', mode: 'full',
    })
    expect(screen.getByLabelText('Indexed repository ID')).toHaveValue('repo-1')
    await user.click(screen.getByRole('button', { name: 'Use this repository for analysis' }))
    expect(onSelectRepository).toHaveBeenCalledWith('repo-1')
  })

  it('renders actual source context with its budget', async () => {
    vi.mocked(platformApi.context).mockResolvedValue({
      repo_id: 'repo-1', budget_used: 18, budget_limit: 12000,
      items: [{ ref: 'lib.py', summary: 'def helper(): pass', extra: { path: 'lib.py' } }],
    })
    const { user } = setup()
    await user.type(screen.getByLabelText('Indexed repository ID'), 'repo-1')
    await user.type(screen.getByLabelText('Source search (blank returns indexed files)'), 'helper')
    await user.click(screen.getByRole('button', { name: 'Retrieve source context' }))
    expect(await screen.findByText('def helper(): pass')).toBeInTheDocument()
    expect(screen.getByText('1 files / 18/12000 characters / repo-1')).toBeInTheDocument()
    expect(platformApi.context).toHaveBeenCalledWith('repo-1', 'helper', 'hybrid')
  })

  it('renders reverse import edges and parsing warnings', async () => {
    vi.mocked(platformApi.impact).mockResolvedValue({
      repo_id: 'repo-1', file: 'lib.py', backend: 'kuzu',
      nodes: [{ path: 'app.py', depth: 1, relationship: 'IMPORTS' }],
      relationships: [{ source: 'app.py', target: 'lib.py', type: 'IMPORTS', line: 2 }],
      warnings: ['Could not parse broken.py'], limitations: [], truncated: false,
    })
    const { user } = setup()
    await user.type(screen.getByLabelText('Indexed repository ID'), 'repo-1')
    await user.type(screen.getByLabelText('Changed file (repository-relative path)'), 'lib.py')
    await user.clear(screen.getByLabelText('Impact depth (1-5)'))
    await user.type(screen.getByLabelText('Impact depth (1-5)'), '3')
    await user.click(screen.getByRole('button', { name: 'Find dependent files' }))
    expect(await screen.findByText('app.py - depth 1')).toBeInTheDocument()
    expect(screen.getByText('app.py:2 -> lib.py (IMPORTS)')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Could not parse broken.py')
    expect(platformApi.impact).toHaveBeenCalledWith('repo-1', 'lib.py', 3)
  })

  it('surfaces graph failures instead of claiming there are no dependents', async () => {
    vi.mocked(platformApi.impact).mockRejectedValue(new Error('Code graph is unavailable'))
    const { user } = setup()
    await user.type(screen.getByLabelText('Indexed repository ID'), 'repo-1')
    await user.type(screen.getByLabelText('Changed file (repository-relative path)'), 'lib.py')
    await user.click(screen.getByRole('button', { name: 'Find dependent files' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Code graph is unavailable')
    expect(screen.queryByText('No statically resolved importers found within this depth.')).not.toBeInTheDocument()
  })

  it('accepts the older external impact response without local-only metadata', async () => {
    vi.mocked(platformApi.impact).mockResolvedValue({
      repo_id: 'repo-1', file: 'lib.py', nodes: [],
    })
    const { user } = setup()
    await user.type(screen.getByLabelText('Indexed repository ID'), 'repo-1')
    await user.type(screen.getByLabelText('Changed file (repository-relative path)'), 'lib.py')
    await user.click(screen.getByRole('button', { name: 'Find dependent files' }))
    expect(await screen.findByText('lib.py / external RAG service / 0 dependent files')).toBeInTheDocument()
  })
})
