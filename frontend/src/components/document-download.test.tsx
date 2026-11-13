import {
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

    documentUrl: (id: string) =>
      `/api/v1/tasks/${id}/document`,

    businessDocumentUrl: (id: string) =>
      `/api/v1/tasks/${id}/business-document`,

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
  'automatically downloads the completed technical Word document only once',
  async () => {
    vi.mocked(
      requirementsApi.download,
    ).mockResolvedValue(
      new Blob(['word']),
    )

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
  'shows both requirements document downloads',
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

    expect(
      screen.getByRole(
        'link',
        {
          name: 'Download Technical Requirements',
        },
      ),
    ).toHaveAttribute(
      'href',
      '/api/v1/tasks/old-task/document',
    )

    expect(
      screen.getByRole(
        'link',
        {
          name: 'Download Non-Technical FRS',
        },
      ),
    ).toHaveAttribute(
      'href',
      '/api/v1/tasks/old-task/business-document',
    )
  },
)


it(
  'shows automatic download failures and keeps both manual downloads available',
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
          name: 'Download Technical Requirements',
        },
      ),
    ).toBeInTheDocument()

    expect(
      screen.getByRole(
        'link',
        {
          name: 'Download Non-Technical FRS',
        },
      ),
    ).toBeInTheDocument()
  },
)