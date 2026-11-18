import { useEffect, useRef, useState } from 'react'
import { errorMessage, requirementsApi, type QTestUploadResult } from '../lib/requirements-api'

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
  const tokenInput = useRef<HTMLInputElement>(null)
  const [projectId, setProjectId] = useState('')
  const [moduleId, setModuleId] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadFailure, setUploadFailure] = useState('')
  const [uploadResult, setUploadResult] = useState<QTestUploadResult | null>(null)

  const upload = async () => {
    const project = Number(projectId)
    const module = moduleId ? Number(moduleId) : null
    const token = tokenInput.current?.value.trim() || ''
    if (!Number.isSafeInteger(project) || project <= 0 ||
      (module !== null && (!Number.isSafeInteger(module) || module <= 0)) || !token) {
      setUploadFailure('Enter a valid project ID, optional module ID, and your qTest token.')
      return
    }
    if (!window.confirm('Create these requirements in qTest? Parent and child requirements will be separate records.')) return
    if (tokenInput.current) tokenInput.current.value = ''
    setUploading(true)
    setUploadFailure('')
    setUploadResult(null)
    try {
      setUploadResult(await requirementsApi.uploadQtest(taskId, project, module, token))
    } catch (error: unknown) {
      setUploadFailure(`${errorMessage(error)}. If the connection was interrupted, check qTest before retrying.`)
    } finally {
      setUploading(false)
    }
  }

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
      <details className="rounded border p-4">
        <summary className="cursor-pointer font-semibold">Upload requirements to qTest</summary>
        <p className="mt-2 text-sm">Your administrator must configure the qTest server. Your token is used only for this upload and is not saved.</p>
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <label className="grid gap-1 text-sm">Project ID
            <input className="rounded border p-2" inputMode="numeric" value={projectId} onChange={(event) => setProjectId(event.target.value)} />
          </label>
          <label className="grid gap-1 text-sm">Module ID (optional)
            <input className="rounded border p-2" inputMode="numeric" value={moduleId} onChange={(event) => setModuleId(event.target.value)} />
          </label>
          <label className="grid gap-1 text-sm">Your qTest token
            <input ref={tokenInput} className="rounded border p-2" type="password" autoComplete="off" />
          </label>
          <button type="button" className="rounded border px-3 py-2" disabled={uploading} onClick={upload}>
            {uploading ? 'Uploading...' : 'Upload to qTest'}
          </button>
        </div>
        {uploadFailure && <p role="alert" className="mt-3">{uploadFailure}</p>}
        {uploadResult && (
          <div className="mt-3 text-sm" role={uploadResult.success ? 'status' : 'alert'}>
            <p>{uploadResult.message}</p>
            {uploadResult.created.length > 0 && <p>Created: {uploadResult.created.map((item) => `${item.requirement_id} → ${item.qtest_id}`).join(', ')}</p>}
            {uploadResult.already_uploaded.length > 0 && <p>Previously uploaded: {uploadResult.already_uploaded.map((item) => `${item.requirement_id} → ${item.qtest_id}`).join(', ')}</p>}
          </div>
        )}
      </details>
    </section>
  )
}