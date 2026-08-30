import { useEffect, useState } from 'react'
import { fetchEvidenceFrameBlobUrl } from '../services/api'

export function EvidenceImage({ analysisId, evidenceId, alt }: { analysisId: string; evidenceId: string; alt: string }) {
  const [url, setUrl] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let objectUrl: string | null = null
    let cancelled = false

    fetchEvidenceFrameBlobUrl(analysisId, evidenceId)
      .then((blobUrl) => {
        if (cancelled) return
        objectUrl = blobUrl
        setUrl(blobUrl)
      })
      .catch(() => !cancelled && setFailed(true))

    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [analysisId, evidenceId])

  if (failed) {
    return <div className="text-xs text-slate-500 italic">Evidence frame unavailable</div>
  }

  if (!url) {
    return <div className="w-full h-40 bg-ink-800 rounded-md animate-pulse" />
  }

  return <img src={url} alt={alt} className="w-full rounded-md border border-ink-700" />
}
