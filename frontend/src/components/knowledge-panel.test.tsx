import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it, vi } from 'vitest'
import { platformApi } from '../lib/platform-api'
import { KnowledgePanel } from './knowledge-panel'

vi.mock('../lib/platform-api', () => ({
  platformApi: {
    search: vi.fn(), answer: vi.fn(), memories: vi.fn(), addMemory: vi.fn(), deleteMemory: vi.fn(),
  },
}))

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><KnowledgePanel projectId="repo" mode="vector" /></QueryClientProvider>)
  return userEvent.setup()
}

beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(platformApi.memories).mockResolvedValue({ memories: [] })
})

it('uses the selected vector mode and renders cited model answers', async () => {
  vi.mocked(platformApi.search).mockResolvedValue({
    nodes: [{ id: 'chunk-1', ref: 'payments.py', text: 'settle_payments()', score: 0.9 }],
    semantic: false, embedding_provider: 'hash',
  })
  vi.mocked(platformApi.answer).mockResolvedValue({
    answer: 'Payments are settled by settle_payments.', citations: ['chunk-1'], session_id: 'session-1',
  })
  const user = setup()
  await user.type(screen.getByLabelText('Question or vector search query'), 'settlement')
  await user.click(screen.getByRole('button', { name: 'Search knowledge chunks' }))
  expect(await screen.findByText('settle_payments()')).toBeInTheDocument()
  expect(platformApi.search).toHaveBeenCalledWith('repo', 'settlement', 'vector')
  await user.click(screen.getByRole('button', { name: 'Ask model with citations' }))
  expect(await screen.findByText('Payments are settled by settle_payments.')).toBeInTheDocument()
  expect(screen.getByText('Source chunk citations: chunk-1')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Ask model with citations' }))
  expect(platformApi.answer).toHaveBeenLastCalledWith('repo', 'settlement', 'vector', 'session-1')
})

it('persists project memories and displays the saved content', async () => {
  vi.mocked(platformApi.addMemory).mockResolvedValue({ success: true })
  const user = setup()
  await screen.findByRole('button', { name: 'Save project memory' })
  vi.mocked(platformApi.memories).mockResolvedValue({
    memories: [{ id: 'm-1', title: 'Graph decision', content: 'Use Kuzu', memory_type: 'decision' }],
  })
  await user.type(screen.getByLabelText('Memory title'), 'Graph decision')
  await user.selectOptions(screen.getByLabelText('Memory type'), 'decision')
  await user.type(screen.getByLabelText('Memory content (do not enter secrets)'), 'Use Kuzu')
  await user.click(screen.getByRole('button', { name: 'Save project memory' }))
  expect(await screen.findByText('Use Kuzu')).toBeInTheDocument()
  expect(platformApi.addMemory).toHaveBeenCalledWith('repo', 'Graph decision', 'Use Kuzu', 'decision')
})