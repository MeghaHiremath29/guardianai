import { useEffect, useState } from 'react'
import { Layout } from '../components/Layout'
import { listEmergencies, type EmergencyOut } from '../services/api'

function formatDuration(startIso: string, endIso: string | null): string {
  if (!endIso) return '—'
  const seconds = Math.round((new Date(endIso + 'Z').getTime() - new Date(startIso + 'Z').getTime()) / 1000)
  if (seconds < 60) return `${seconds}s`
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
}

const STATUS_BADGE: Record<string, string> = {
  RESOLVED: 'text-signal-normal',
  FALSE_ALARM: 'text-slate-500',
}

export function History() {
  const [emergencies, setEmergencies] = useState<EmergencyOut[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    listEmergencies().then((data) => {
      setEmergencies(data.filter((e) => e.status === 'RESOLVED' || e.status === 'FALSE_ALARM'))
      setIsLoading(false)
    })
  }, [])

  return (
    <Layout>
      <div className="px-8 py-6">
        <h2 className="text-xl font-semibold text-slate-50">Emergency History</h2>
        <p className="text-sm text-slate-500 mt-0.5 mb-6">
          Closed incidents — resolved or marked as false alarms.
        </p>

        <div className="panel overflow-hidden">
          {isLoading && <p className="p-4 text-sm text-slate-500">Loading…</p>}
          {!isLoading && emergencies.length === 0 && (
            <p className="p-4 text-sm text-slate-500">
              No closed incidents yet. Resolve or mark false-alarm on an emergency from Live Emergencies
              to see it here.
            </p>
          )}
          {emergencies.length > 0 && (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-500 border-b border-ink-700">
                  <th className="px-4 py-2 font-normal">Event</th>
                  <th className="px-4 py-2 font-normal">Severity</th>
                  <th className="px-4 py-2 font-normal">Outcome</th>
                  <th className="px-4 py-2 font-normal">Detected</th>
                  <th className="px-4 py-2 font-normal">Time to close</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-700">
                {emergencies.map((e) => (
                  <tr key={e.id}>
                    <td className="px-4 py-3 text-slate-200">{e.event_type.replace(/_/g, ' ')}</td>
                    <td className="px-4 py-3 text-slate-400 font-mono text-xs">{e.severity}</td>
                    <td className={`px-4 py-3 font-mono text-xs ${STATUS_BADGE[e.status] ?? ''}`}>
                      {e.status === 'FALSE_ALARM' ? 'False alarm' : 'Resolved'}
                    </td>
                    <td className="px-4 py-3 text-slate-500 text-xs">
                      {new Date(e.created_at + 'Z').toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-slate-500 text-xs">
                      {formatDuration(e.created_at, e.resolved_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </Layout>
  )
}
