import { useEffect, useState, useCallback } from 'react'
import { isAxiosError } from 'axios'
import { Layout } from '../components/Layout'
import {
  acknowledgeEmergency,
  getEmergency,
  listEmergencies,
  markFalseAlarm,
  resolveEmergency,
  type EmergencyDetailOut,
  type EmergencyOut,
  type EmergencySeverity,
} from '../services/api'

const SEVERITY_STYLES: Record<EmergencySeverity, string> = {
  CRITICAL: 'bg-signal-critical/15 text-signal-critical border-signal-critical/30',
  HIGH: 'bg-signal-high/15 text-signal-high border-signal-high/30',
  WARNING: 'bg-signal-warning/15 text-signal-warning border-signal-warning/30',
  NORMAL: 'bg-signal-normal/15 text-signal-normal border-signal-normal/30',
}

const STATUS_LABEL: Record<string, string> = {
  OPEN: 'Open',
  ACKNOWLEDGED: 'Acknowledged',
  RESOLVED: 'Resolved',
  FALSE_ALARM: 'False alarm',
}

function timeAgo(iso: string): string {
  const seconds = Math.floor((Date.now() - new Date(iso + 'Z').getTime()) / 1000)
  if (seconds < 60) return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  return `${Math.floor(seconds / 3600)}h ago`
}

export function Emergencies() {
  const [emergencies, setEmergencies] = useState<EmergencyOut[]>([])
  const [selected, setSelected] = useState<EmergencyDetailOut | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [actionError, setActionError] = useState<string | null>(null)
  const [actionPending, setActionPending] = useState(false)
  const [filter, setFilter] = useState<'ACTIVE' | 'ALL'>('ACTIVE')

  const refresh = useCallback(async () => {
    const data = await listEmergencies()
    setEmergencies(data)
    setIsLoading(false)
  }, [])

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 5000) // simple polling — see README for the SSE upgrade path
    return () => clearInterval(interval)
  }, [refresh])

  const openDetail = async (id: string) => {
    setActionError(null)
    const detail = await getEmergency(id)
    setSelected(detail)
  }

  const runAction = async (action: (id: string) => Promise<EmergencyDetailOut>) => {
    if (!selected) return
    setActionPending(true)
    setActionError(null)
    try {
      const updated = await action(selected.id)
      setSelected(updated)
      await refresh()
    } catch (err) {
      if (isAxiosError(err) && err.response?.status === 403) {
        setActionError('Only a caretaker or admin can take this action.')
      } else if (isAxiosError(err) && err.response?.status === 409) {
        setActionError('This emergency has already reached a final state.')
      } else {
        setActionError('Something went wrong. Please try again.')
      }
    } finally {
      setActionPending(false)
    }
  }

  const visible = filter === 'ACTIVE'
    ? emergencies.filter((e) => e.status === 'OPEN' || e.status === 'ACKNOWLEDGED')
    : emergencies

  return (
    <Layout>
      <div className="px-8 py-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-semibold text-slate-50">Live Emergencies</h2>
            <p className="text-sm text-slate-500 mt-0.5">
              Polls every 5s. Acknowledging or resolving here stops further escalation automatically.
            </p>
          </div>
          <div className="flex gap-1 bg-ink-900 border border-ink-700 rounded-md p-1">
            {(['ACTIVE', 'ALL'] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1 text-xs rounded ${filter === f ? 'bg-ink-800 text-slate-100' : 'text-slate-500'}`}
              >
                {f === 'ACTIVE' ? 'Active' : 'All'}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="panel divide-y divide-ink-700">
            {isLoading && <p className="p-4 text-sm text-slate-500">Loading…</p>}
            {!isLoading && visible.length === 0 && (
              <p className="p-4 text-sm text-slate-500">
                No {filter === 'ACTIVE' ? 'active' : ''} emergencies. Run a fall simulation from Sensor
                Monitor to generate one.
              </p>
            )}
            {visible.map((e) => (
              <button
                key={e.id}
                onClick={() => openDetail(e.id)}
                className={`w-full text-left px-4 py-3 hover:bg-ink-800/60 transition-colors ${
                  selected?.id === e.id ? 'bg-ink-800' : ''
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className={`text-[10px] font-mono uppercase border rounded px-1.5 py-0.5 ${SEVERITY_STYLES[e.severity]}`}>
                    {e.severity}
                  </span>
                  <span className="text-xs text-slate-500">{timeAgo(e.created_at)}</span>
                </div>
                <p className="text-sm text-slate-200">
                  {e.event_type.replace(/_/g, ' ')} — {Math.round(e.confidence * 100)}% confidence
                </p>
                <p className="text-xs text-slate-500 mt-0.5">{STATUS_LABEL[e.status]}</p>
              </button>
            ))}
          </div>

          <div className="panel p-5">
            {!selected && (
              <p className="text-sm text-slate-500">Select an emergency to see its full timeline.</p>
            )}
            {selected && (
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className={`text-xs font-mono uppercase border rounded px-2 py-1 ${SEVERITY_STYLES[selected.severity]}`}>
                    {selected.severity}
                  </span>
                  <span className="text-xs text-slate-500">{STATUS_LABEL[selected.status]}</span>
                </div>

                <h3 className="text-base font-medium text-slate-100">
                  {selected.event_type.replace(/_/g, ' ')}
                </h3>
                <p className="text-xs text-slate-500 mt-1">
                  Confidence {Math.round(selected.confidence * 100)}% — this is an AI risk estimate, not a
                  medical diagnosis.
                </p>

                {selected.reasons.length > 0 && (
                  <ul className="mt-3 text-sm text-slate-400 list-disc list-inside space-y-0.5">
                    {selected.reasons.map((r) => (
                      <li key={r}>{r}</li>
                    ))}
                  </ul>
                )}

                <div className="mt-4 border-t border-ink-700 pt-4">
                  <p className="text-xs text-slate-500 mb-2">Timeline</p>
                  <ol className="space-y-2">
                    {selected.timeline.map((t) => (
                      <li key={t.id} className="text-xs text-slate-400 font-mono">
                        <span className="text-slate-600">{new Date(t.timestamp + 'Z').toLocaleTimeString()}</span>
                        {' — '}
                        <span className="text-slate-300 font-body">{t.event_text}</span>
                      </li>
                    ))}
                  </ol>
                </div>

                {actionError && (
                  <p className="mt-4 text-xs text-signal-critical bg-signal-critical/10 border border-signal-critical/30 rounded-md px-3 py-2">
                    {actionError}
                  </p>
                )}

                {(selected.status === 'OPEN' || selected.status === 'ACKNOWLEDGED') && (
                  <div className="mt-4 flex gap-2">
                    {selected.status === 'OPEN' && (
                      <button
                        onClick={() => runAction(acknowledgeEmergency)}
                        disabled={actionPending}
                        className="text-xs bg-accent hover:bg-accent/90 disabled:opacity-50 text-white rounded-md px-3 py-2 transition-colors"
                      >
                        Acknowledge
                      </button>
                    )}
                    <button
                      onClick={() => runAction(resolveEmergency)}
                      disabled={actionPending}
                      className="text-xs bg-signal-normal hover:opacity-90 disabled:opacity-50 text-white rounded-md px-3 py-2 transition-colors"
                    >
                      Resolve
                    </button>
                    <button
                      onClick={() => runAction(markFalseAlarm)}
                      disabled={actionPending}
                      className="text-xs border border-ink-700 hover:bg-ink-800 disabled:opacity-50 text-slate-300 rounded-md px-3 py-2 transition-colors"
                    >
                      False alarm
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  )
}
