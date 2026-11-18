import {
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react'

import {
  beforeEach,
  expect,
  it,
  vi,
} from 'vitest'

import { requirementsApi } from '../lib/requirements-api'
import { DocumentDownload } from './document-download'


vi.mock('../lib/requirements-api', () => ({
  requirementsApi: {
    download: vi.fn(),
    uploadQtest: vi.fn(),

    documentUrl: (id: string) =>
      `/api/v1/tasks/${id}/document`,

    qtestUrl: (id: string) =>
      `/api/v1/tasks/${id}/qtest-xlsx`,

    artifactsUrl: (id: string) =>
      `/api/v1/tasks/${id}/artifacts.zip`,

    analysisUrl: (id: string) =>
      `/api/v1/tasks/${id}/analysis`,
  },

  errorMessage: (error: Error) =>
    error.message,
}))


beforeEach(() => {
  vi.resetAllMocks()
})


it(
  'automatically downloads the consolidated requirements DOCX only once',
  async () => {
    vi.mocked(
      requirementsApi.download,
    ).mockResolvedValue(
      new Blob(['word']),
    )

    it('requires confirmation and clears the token before reporting a partial upload', async () => {
      vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
      vi.mocked(requirementsApi.uploadQtest).mockResolvedValue({
        success: false,
        message: 'The second upload is uncertain.',
        created: [{ requirement_id: 'REQ-1', qtest_id: '25' }],
        already_uploaded: [],
      })
      render(<DocumentDownload taskId="task-1" automatically={false} />)
      fireEvent.click(screen.getByText('Upload requirements to qTest'))
      fireEvent.change(screen.getByLabelText('Project ID'), { target: { value: '7' } })
      fireEvent.change(screen.getByLabelText('Your qTest token'), { target: { value: 'private-token' } })
      fireEvent.click(screen.getByRole('button', { name: 'Upload to qTest' }))
      expect(requirementsApi.uploadQtest).not.toHaveBeenCalled()
      fireEvent.click(screen.getByRole('button', { name: 'Upload to qTest' }))
      expect(await screen.findByRole('alert')).toHaveTextContent('The second upload is uncertain.')
      expect(screen.getByRole('alert')).toHaveTextContent('REQ-1 → 25')
      expect(screen.getByLabelText('Your qTest token')).toHaveValue('')
      expect(requirementsApi.uploadQtest).toHaveBeenCalledWith('task-1', 7, null, 'private-token')
      vi.restoreAllMocks()
    })

    const create = vi.fn(
      () => 'blob:test-document',
    )

    Object.defineProperty(
      URL,
      'createObjectURL',
      {
        configurable: true,
        value: create,
      },
    )

    Object.defineProperty(
      URL,
      'revokeObjectURL',
      {
        configurable: true,
        value: vi.fn(),
      },
    )

    const click = vi
      .spyOn(
        HTMLAnchorElement.prototype,
        'click',
      )
      .mockImplementation(() => {})

    const { rerender } = render(
      <DocumentDownload
        taskId="task-1"
        automatically
      />,
    )

    await waitFor(() =>
      expect(click).toHaveBeenCalledOnce(),
    )

    expect(
      requirementsApi.download,
    ).toHaveBeenCalledWith('task-1')

    expect(
      create,
    ).toHaveBeenCalledOnce()

    rerender(
      <DocumentDownload
        taskId="task-1"
        automatically
      />,
    )

    expect(
      requirementsApi.download,
    ).toHaveBeenCalledOnce()

    click.mockRestore()
  },
)


it(
  'shows the all-artifacts ZIP and individual final output downloads',
  () => {
    render(
      <DocumentDownload
        taskId="old-task"
        automatically={false}
      />,
    )

    expect(
      requirementsApi.download,
    ).not.toHaveBeenCalled()

    expect(screen.getByRole('link', { name: 'Download all artifacts (ZIP)' }))
      .toHaveAttribute('href', '/api/v1/tasks/old-task/artifacts.zip')

    expect(
      screen.getByRole(
        'link',
        {
          name: 'Final requirements DOCX',
        },
      ),
    ).toHaveAttribute(
      'href',
      '/api/v1/tasks/old-task/document',
    )

    expect(screen.getByRole('link', { name: 'Canonical requirements JSON' }))
      .toHaveAttribute('href', '/api/v1/tasks/old-task/analysis')
    expect(screen.getByRole('link', { name: 'qTest requirements XLSX' }))
      .toHaveAttribute('href', '/api/v1/tasks/old-task/qtest-xlsx')
    expect(screen.getAllByRole('link')).toHaveLength(4)
  },
)


it(
  'shows automatic download failures and keeps all final output links available',
  async () => {
    vi.mocked(
      requirementsApi.download,
    ).mockRejectedValue(
      new Error('Network failed'),
    )

    render(
      <DocumentDownload
        taskId="task-1"
        automatically
      />,
    )

    expect(
      await screen.findByRole('alert'),
    ).toHaveTextContent(
      'Automatic download failed: Network failed',
    )

    expect(
      screen.getByRole(
        'link',
        {
          name: 'Final requirements DOCX',
        },
      ),
    ).toBeInTheDocument()

    expect(
      screen.getByRole(
        'link',
        {
          name: 'qTest requirements XLSX',
        },
      ),
    ).toBeInTheDocument()
  },
)