import { useEffect, useRef, useState } from 'react'
import { errorMessage, requirementsApi } from '../lib/requirements-api'

export function DocumentDownload({
  taskId,
  automatically,
  projectName = 'Project',
}: {
  taskId: string
  automatically: boolean
  projectName?: string
}) {
  const started = useRef<string | null>(null)
  const [failure, setFailure] = useState('')

  useEffect(() => {
    if (!automatically || started.current === taskId) return
    started.current = taskId
    requirementsApi
      .download(taskId)
      .then((document) => {
        const url = URL.createObjectURL(document)
        const link = window.document.createElement('a')
        link.href = url
        const slug = projectName.replace(/[^A-Za-z0-9._-]+/g, '-').replace(/^-|-$/g, '') || 'project'
        link.download = `TIP-Final-Requirements-${slug}.docx`
        window.document.body.appendChild(link)
        link.click()
        link.remove()
        window.setTimeout(() => URL.revokeObjectURL(url), 1000)
      })
      .catch((error: unknown) => setFailure(errorMessage(error)))
  }, [automatically, projectName, taskId])

  return (
    <section className="space-y-3">
      {failure && (
        <p role="alert">
          Automatic DOCX download failed: {failure}. Use the links below to retry.
        </p>
      )}
      <h3 className="font-semibold">Requirements generated</h3>
      <div className="flex flex-wrap gap-4">
        <a className="underline font-semibold" href={requirementsApi.artifactsUrl(taskId)} download>
          Download all artifacts (ZIP)
        </a>
        <a className="underline" href={requirementsApi.documentUrl(taskId)} download>
          Final requirements DOCX
        </a>
        <a className="underline" href={requirementsApi.analysisUrl(taskId)} download>
          Canonical requirements JSON
        </a>
        <a className="underline" href={requirementsApi.qtestUrl(taskId)} download>
          qTest requirements XLSX
        </a>
      </div>
    </section>
  )
}