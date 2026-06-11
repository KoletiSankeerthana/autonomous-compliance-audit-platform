import { useRef, useState } from 'react'
import { documentsApi } from '../api/documents'
import { extractErrorMessage } from '../utils/errors'
import type { UploadResponse } from '../types/audit'

const DOCUMENT_TYPES = [
  { value: 'policy',     label: 'Company Policy' },
  { value: 'regulation', label: 'Regulation / Standard' },
  { value: 'general',    label: 'General Document' },
]

type DriveStatus = UploadResponse['drive_upload_status']

interface DriveStatusConfig {
  label: string
  description: string
  color: string
  iconPath: string
}

const DRIVE_STATUS_CONFIG: Record<DriveStatus, DriveStatusConfig> = {
  uploaded: {
    label: 'Uploaded to Google Drive',
    description: 'File is now available in your configured Google Drive folder.',
    color: 'text-green-700 dark:text-green-400',
    iconPath: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
  },
  duplicate: {
    label: 'Already in Google Drive',
    description: 'A file with this name already exists in Drive. Existing metadata reused.',
    color: 'text-blue-700 dark:text-blue-400',
    iconPath: 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  },
  failed: {
    label: 'Drive Upload Failed',
    description: 'Document saved locally. Drive upload failed — check server logs.',
    color: 'text-amber-700 dark:text-amber-400',
    iconPath: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z',
  },
  skipped: {
    label: 'Google Drive Not Configured',
    description: 'Set GOOGLE_DRIVE_ENABLED=true in environment settings to enable Drive integration.',
    color: 'text-gray-500 dark:text-gray-400',
    iconPath: 'M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636',
  },
}

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null)
  const [docType, setDocType] = useState('policy')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<UploadResponse | null>(null)
  const [error, setError] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    const dropped = e.dataTransfer.files[0]
    if (dropped?.name.toLowerCase().endsWith('.pdf')) {
      setFile(dropped)
      setError('')
    } else {
      setError('Only PDF files are accepted.')
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0]
    if (selected) {
      setFile(selected)
      setError('')
      setResult(null)
    }
  }

  const handleUpload = async () => {
    if (!file) { setError('Please select a file.'); return }
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const res = await documentsApi.upload(file, docType)
      setResult(res)
    } catch (err: unknown) {
      setError(extractErrorMessage(err) ?? 'Upload failed.')
    } finally {
      setLoading(false)
    }
  }

  const driveStatusConfig = result
    ? DRIVE_STATUS_CONFIG[result.drive_upload_status ?? 'skipped']
    : null

  return (
    <div className="max-w-2xl space-y-5">
      <div>
        <h1 className="page-heading">Upload Documents</h1>
        <p className="page-subheading mt-1">
          Upload PDF policy or regulation documents for AI-powered compliance analysis.
          Documents are automatically synced to Google Drive when configured.
        </p>
      </div>

      {/* Document type selector */}
      <div className="card p-5">
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Document Type
        </label>
        <div className="flex flex-col sm:flex-row gap-3">
          {DOCUMENT_TYPES.map((dt) => (
            <button
              key={dt.value}
              onClick={() => setDocType(dt.value)}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                docType === dt.value
                  ? 'bg-brand-600 text-white'
                  : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
              }`}
            >
              {dt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Drop zone */}
      <div
        className={`card p-8 border-2 border-dashed transition-colors cursor-pointer ${
          file
            ? 'border-brand-500 bg-brand-50 dark:bg-brand-950/10'
            : 'border-gray-300 dark:border-gray-700 hover:border-brand-400'
        }`}
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          className="hidden"
          onChange={handleFileChange}
        />
        <div className="text-center">
          <svg className="mx-auto w-10 h-10 text-gray-400 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          {file ? (
            <div>
              <p className="font-medium text-brand-600 dark:text-brand-400">{file.name}</p>
              <p className="text-xs text-gray-500 mt-1">
                {(file.size / 1024 / 1024).toFixed(2)} MB
              </p>
            </div>
          ) : (
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Drop a PDF here, or click to browse
              </p>
              <p className="text-xs text-gray-400 mt-1">Maximum file size: 50 MB</p>
            </div>
          )}
        </div>
      </div>

      {error && (
        <div className="px-4 py-3 rounded-md bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-sm text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      <button
        id="upload-submit-btn"
        onClick={handleUpload}
        disabled={!file || loading}
        className="btn-primary"
      >
        {loading ? 'Processing...' : 'Upload and Ingest'}
      </button>

      {/* Result */}
      {result && (
        <div className="card p-5 border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/10 space-y-4">
          <p className="text-sm font-semibold text-green-800 dark:text-green-400">
            Document ingested successfully
          </p>

          {/* Core ingestion metrics */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
            <div>
              <span className="text-gray-500">Filename</span>
              <p className="font-medium text-gray-900 dark:text-white truncate">{result.filename}</p>
            </div>
            <div>
              <span className="text-gray-500">Document Type</span>
              <p className="font-medium text-gray-900 dark:text-white capitalize">{result.document_type}</p>
            </div>
            <div>
              <span className="text-gray-500">Characters Extracted</span>
              <p className="font-medium text-gray-900 dark:text-white">{result.characters.toLocaleString()}</p>
            </div>
            <div>
              <span className="text-gray-500">Chunks Stored</span>
              <p className="font-medium text-gray-900 dark:text-white">{result.chunks}</p>
            </div>
          </div>

          {/* Divider */}
          <div className="border-t border-green-200 dark:border-green-800" />

          {/* Google Drive status */}
          {driveStatusConfig && (
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                Google Drive
              </p>
              <div className="flex items-start gap-2">
                <svg
                  className={`w-5 h-5 mt-0.5 flex-shrink-0 ${driveStatusConfig.color}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d={driveStatusConfig.iconPath} />
                </svg>
                <div className="min-w-0">
                  <p className={`text-sm font-medium ${driveStatusConfig.color}`}>
                    {driveStatusConfig.label}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                    {driveStatusConfig.description}
                  </p>

                  {/* Drive file details */}
                  {result.drive_file_id && (
                    <div className="mt-2 space-y-1 text-xs text-gray-600 dark:text-gray-400">
                      <p>
                        <span className="font-medium">File ID:</span>{' '}
                        <code className="font-mono">{result.drive_file_id}</code>
                      </p>
                      {result.drive_file_name && result.drive_file_name !== result.filename && (
                        <p>
                          <span className="font-medium">Drive filename:</span>{' '}
                          {result.drive_file_name}
                        </p>
                      )}
                    </div>
                  )}

                  {/* Open in Drive link */}
                  {result.drive_web_view_link && (
                    <a
                      id="drive-view-link"
                      href={result.drive_web_view_link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 mt-2 text-xs font-medium text-brand-600 dark:text-brand-400 hover:underline"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                          d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                      </svg>
                      Open in Google Drive
                    </a>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
