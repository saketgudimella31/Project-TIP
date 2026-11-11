import { useEffect, useRef, useState } from 'react'
import { errorMessage, requirementsApi } from '../lib/requirements-api'

export function DocumentDownload({ taskId, automatically }: { taskId: string; automatically: boolean }) {
  const started = useRef<string | null>(null)
  const [failure, setFailure] = useState('')
  useEffect(() => {
    if (!automatically || started.current === taskId) return
    started.current = taskId
    requirementsApi.download(taskId).then((document) => {
      const url = URL.createObjectURL(document)
      const link = window.document.createElement('a')
      link.href = url
      link.download = `TIP-requirements-${taskId}.docx`
      window.document.body.appendChild(link)
      link.click()
      link.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    }).catch((error: unknown) => setFailure(errorMessage(error)))
  }, [automatically, taskId])
  return <div className="space-y-2">
    {failure && <p role="alert">Automatic download failed: {failure}. Use the download link to retry.</p>}
    <div className="flex gap-4">
      <a className="underline" href={requirementsApi.documentUrl(taskId)} download>Download Word document</a>
      <a className="underline" href={requirementsApi.analysisUrl(taskId)} target="_blank" rel="noreferrer">Structured analysis JSON</a>
    </div>
  </div>
}