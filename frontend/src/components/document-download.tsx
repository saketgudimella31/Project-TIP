import { useEffect, useRef, useState } from 'react'
import { errorMessage, requirementsApi } from '../lib/requirements-api'

export function DocumentDownload({
  taskId,
  automatically,
}: {
  taskId: string
  automatically: boolean
}) {
  const started = useRef<string | null>(null)
  const [failure, setFailure] = useState('')

  useEffect(() => {
    if (!automatically || started.current === taskId) return

    started.current = taskId

    // Automatically download only the technical document.
    // Both documents remain available through the links below.
    requirementsApi
      .download(taskId)
      .then((document) => {
        const url = URL.createObjectURL(document)
        const link = window.document.createElement('a')

        link.href = url
        link.download = `TIP-technical-requirements-${taskId}.docx`

        window.document.body.appendChild(link)
        link.click()
        link.remove()

        window.setTimeout(
          () => URL.revokeObjectURL(url),
          1000,
        )
      })
      .catch((error: unknown) =>
        setFailure(errorMessage(error)),
      )
  }, [automatically, taskId])

  return (
    <div className="space-y-4">
      {failure && (
        <p role="alert">
          Automatic download failed: {failure}. Use the
          download links below to retry.
        </p>
      )}

      <div>
        <p className="font-medium">
          Technical Requirements
        </p>

        <p className="text-sm">
          Detailed requirements, implementation evidence,
          traceability, and UML information.
        </p>

        <a
          className="underline"
          href={requirementsApi.documentUrl(taskId)}
          download
        >
          Download Technical Requirements
        </a>
      </div>

      <div>
        <p className="font-medium">
          Non-Technical Functional Requirements
        </p>

        <p className="text-sm">
          Business-facing Functional Requirements
          Specification for product, operations, management,
          and other non-technical stakeholders.
        </p>

        <a
          className="underline"
          href={requirementsApi.businessDocumentUrl(taskId)}
          download
        >
          Download Non-Technical FRS
        </a>
      </div>

      <div>
        <a
          className="underline"
          href={requirementsApi.analysisUrl(taskId)}
          target="_blank"
          rel="noreferrer"
        >
          Structured analysis JSON
        </a>
      </div>
    </div>
  )
}