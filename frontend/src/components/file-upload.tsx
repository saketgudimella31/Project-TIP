import { useRef } from 'react'
import { FileCheck2, Upload, X, type LucideIcon } from 'lucide-react'
import { Button } from './ui/button'

interface FileUploadProps {
  id: string
  title: string
  action: string
  formats?: string
  accept?: string
  folder?: boolean
  files: File[]
  icon: LucideIcon
  onChange: (files: File[]) => void
}

export function FileUpload({
  id, title, action, formats, accept, folder, files, icon: Icon, onChange,
}: FileUploadProps) {
  const input = useRef<HTMLInputElement>(null)
  return (
    <section className="rounded-lg border border-slate-300 bg-slate-50 p-4">
      <div className="mb-4 flex items-center gap-3">
        <span className="rounded-lg bg-blue-100 p-2 text-blue-800">
          <Icon className="h-5 w-5" aria-hidden="true" />
        </span>
        <div>
          <h3 className="font-semibold">{title}</h3>
          {formats && <p className="mt-1 text-xs text-slate-600">{formats}</p>}
        </div>
      </div>
      <input
        ref={input}
        id={id}
        className="hidden"
        type="file"
        aria-label={title}
        multiple
        accept={accept}
        {...(folder ? { webkitdirectory: '', directory: '' } : {})}
        onChange={(event) => {
          onChange(Array.from(event.target.files ?? []))
          event.target.value = ''
        }}
      />
      <Button
        type="button"
        className="w-full border border-blue-700 bg-blue-700 text-white shadow-sm hover:bg-blue-800"
        onClick={() => input.current?.click()}
      >
        <Upload className="mr-2 h-4 w-4" aria-hidden="true" />{action}
      </Button>
      {files.length > 0 && (
        <div className="mt-3 space-y-2">
          <div className="flex items-center justify-between gap-2">
            <p role="status" className="flex items-center gap-2 text-sm text-green-800">
              <FileCheck2 className="h-4 w-4" aria-hidden="true" />
              {files.length} {files.length === 1 ? 'file' : 'files'}
            </p>
            <Button type="button" variant="ghost" size="sm"
              aria-label={`Clear ${title.toLowerCase()}`} onClick={() => onChange([])}>
              <X className="mr-1 h-4 w-4" aria-hidden="true" />Clear
            </Button>
          </div>
          <ul className="max-h-32 space-y-1 overflow-y-auto text-xs text-slate-700" aria-label={`${title} files`}>
            {files.map((file, index) => (
              <li className="break-all" key={`${file.webkitRelativePath || file.name}-${index}`}>
                {file.webkitRelativePath || file.name}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}