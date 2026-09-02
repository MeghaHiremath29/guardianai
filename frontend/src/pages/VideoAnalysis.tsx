import { useEffect, useRef, useState } from 'react'
import { isAxiosError } from 'axios'
import { Layout } from '../components/Layout'
import { EvidenceImage } from '../components/EvidenceImage'
import {
  listPeople,
  listVideoAnalyses,
  uploadVideoForAnalysis,
  type AnalysisType,
  type Person,
  type VideoAnalysisOut,
} from '../services/api'

const SEVERITY_STYLES: Record<string, string> = {
  CRITICAL: 'bg-signal-critical/15 text-signal-critical border-signal-critical/30',
  HIGH: 'bg-signal-high/15 text-signal-high border-signal-high/30',
  WARNING: 'bg-signal-warning/15 text-signal-warning border-signal-warning/30',
  NORMAL: 'bg-signal-normal/15 text-signal-normal border-signal-normal/30',
}

export function VideoAnalysis() {
  const [analyses, setAnalyses] = useState<VideoAnalysisOut[]>([])
  const [people, setPeople] = useState<Person[]>([])
  const [isLoading, setIsLoading] = useState(true)

  const [analysisType, setAnalysisType] = useState<AnalysisType>('TRAFFIC_ACCIDENT')
  const [personId, setPersonId] = useState<string>('')
  const [isUploading, setIsUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const refresh = async () => {
    const data = await listVideoAnalyses()
    setAnalyses(data)
    setIsLoading(false)
  }

  useEffect(() => {
    refresh()
    listPeople().then(setPeople)
  }, [])

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploadError(null)
    setIsUploading(true)
    try {
      await uploadVideoForAnalysis(file, analysisType, personId || undefined)
      await refresh()
    } catch (err) {
      if (isAxiosError(err) && err.response?.status === 400) {
        setUploadError(err.response.data?.detail ?? 'Invalid file for this analysis type.')
      } else if (isAxiosError(err) && err.response?.status === 413) {
        setUploadError('File is too large.')
      } else {
        setUploadError('Something went wrong while analyzing this file.')
      }
    } finally {
      setIsUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  return (
    <Layout>
      <div className="px-8 py-6">
        <h2 className="text-xl font-semibold text-slate-50">Video Analysis</h2>
        <p className="text-sm text-slate-500 mt-0.5 mb-6">
          Upload real footage — this runs actual OpenCV analysis, not a scripted result. See{' '}
          <span className="text-slate-400">docs/ai_models.md</span> for exactly how each detector works
          and its known limitations.
        </p>

        <div className="panel p-5 mb-6 max-w-xl">
          <h3 className="text-sm font-medium text-slate-200 mb-3">Analyze new footage</h3>

          <div className="flex gap-2 mb-3">
            {(['TRAFFIC_ACCIDENT', 'FIRE_SMOKE'] as const).map((t) => (
              <button
                key={t}
                onClick={() => setAnalysisType(t)}
                className={`text-xs px-3 py-1.5 rounded-md border transition-colors ${
                  analysisType === t
                    ? 'bg-accent/15 border-accent/40 text-accent'
                    : 'border-ink-700 text-slate-400 hover:bg-ink-800'
                }`}
              >
                {t === 'TRAFFIC_ACCIDENT' ? 'Traffic accident (video only)' : 'Fire / smoke (image or video)'}
              </button>
            ))}
          </div>

          <select
            value={personId}
            onChange={(e) => setPersonId(e.target.value)}
            className="w-full mb-3 rounded-md bg-ink-800 border border-ink-700 px-3 py-2 text-sm text-slate-100 focus:border-accent focus:outline-none"
          >
            <option value="">No monitored person (general footage)</option>
            {people.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>

          <label className="block">
            <input
              ref={fileInputRef}
              type="file"
              accept={analysisType === 'TRAFFIC_ACCIDENT' ? '.mp4,.avi,.mov' : '.mp4,.avi,.mov,.jpg,.jpeg,.png'}
              onChange={handleUpload}
              disabled={isUploading}
              className="hidden"
              id="video-upload-input"
            />
            <span
              onClick={() => fileInputRef.current?.click()}
              className={`block text-center text-sm border border-dashed border-ink-700 rounded-md py-6 cursor-pointer transition-colors ${
                isUploading ? 'opacity-50' : 'hover:bg-ink-800/50 hover:border-accent/50'
              }`}
            >
              {isUploading ? 'Analyzing… this runs real frame-by-frame CV, please wait' : 'Click to choose a file'}
            </span>
          </label>

          {uploadError && (
            <p className="mt-3 text-xs text-signal-critical bg-signal-critical/10 border border-signal-critical/30 rounded-md px-3 py-2">
              {uploadError}
            </p>
          )}
        </div>

        <h3 className="text-sm font-medium text-slate-200 mb-3">Analysis history</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {isLoading && <p className="text-sm text-slate-500">Loading…</p>}
          {!isLoading && analyses.length === 0 && (
            <p className="text-sm text-slate-500 col-span-full">
              No analyses yet — upload a video or image above.
            </p>
          )}
          {analyses.map((a) => (
            <div key={a.id} className="panel p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-slate-500">{a.analysis_type.replace('_', ' ')}</span>
                {a.severity && (
                  <span className={`text-[10px] font-mono uppercase border rounded px-1.5 py-0.5 ${SEVERITY_STYLES[a.severity]}`}>
                    {a.severity}
                  </span>
                )}
              </div>

              <p className="text-sm text-slate-200 truncate mb-1">{a.original_filename}</p>

              {a.status === 'PROCESSING' && <p className="text-xs text-slate-500">Processing…</p>}
              {a.status === 'FAILED' && (
                <p className="text-xs text-signal-critical">Analysis failed: {a.error_detail}</p>
              )}
              {a.status === 'COMPLETED' && (
                <>
                  <p className="text-xs text-slate-500 mb-2">
                    {a.detected ? 'Detected' : 'Not detected'} — {Math.round((a.confidence ?? 0) * 100)}% confidence
                  </p>
                  {a.reasons.length > 0 && (
                    <ul className="text-xs text-slate-400 list-disc list-inside mb-2 space-y-0.5">
                      {a.reasons.map((r) => <li key={r}>{r}</li>)}
                    </ul>
                  )}
                  {a.evidence.filter((e) => e.file_type === 'evidence_frame').map((e) => (
                    <EvidenceImage key={e.id} analysisId={a.id} evidenceId={e.id} alt="Evidence frame" />
                  ))}
                  {a.emergency_id && (
                    <p className="text-xs text-accent mt-2">→ Created emergency</p>
                  )}
                </>
              )}
            </div>
          ))}
        </div>
      </div>
    </Layout>
  )
}
