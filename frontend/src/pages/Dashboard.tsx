import { useEffect, useState } from 'react'
import { Layout } from '../components/Layout'
import { useAuth } from '../context/AuthContext'
import { listDevices, listEmergencies, type Device, type EmergencyOut } from '../services/api'

function averageResponseTime(emergencies: EmergencyOut[]): string {
  const resolved = emergencies.filter((e) => e.status === 'RESOLVED' && e.resolved_at)
  if (resolved.length === 0) return '—'
  const totalSeconds = resolved.reduce((sum, e) => {
    return sum + (new Date(e.resolved_at! + 'Z').getTime() - new Date(e.created_at + 'Z').getTime()) / 1000
  }, 0)
  const avgSeconds = Math.round(totalSeconds / resolved.length)
  return avgSeconds < 60 ? `${avgSeconds}s` : `${Math.floor(avgSeconds / 60)}m ${avgSeconds % 60}s`
}

export function Dashboard() {
  const { user } = useAuth()
  const [emergencies, setEmergencies] = useState<EmergencyOut[]>([])
  const [devices, setDevices] = useState<Device[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    Promise.all([listEmergencies(), listDevices()]).then(([e, d]) => {
      setEmergencies(e)
      setDevices(d)
      setIsLoading(false)
    })
  }, [])

  const active = emergencies.filter((e) => e.status === 'OPEN' || e.status === 'ACKNOWLEDGED')
  const criticalCount = active.filter((e) => e.severity === 'CRITICAL').length
  const highWarningCount = active.filter((e) => e.severity === 'HIGH' || e.severity === 'WARNING').length
  const devicesOnline = devices.filter((d) => d.status === 'ONLINE').length
  const recentEmergencies = [...emergencies]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5)

  const stats = [
    { label: 'Critical emergencies', value: isLoading ? '—' : String(criticalCount) },
    { label: 'High / warning events', value: isLoading ? '—' : String(highWarningCount) },
    { label: 'Devices online', value: isLoading ? '—' : `${devicesOnline} / ${devices.length}` },
    { label: 'Avg. response time', value: isLoading ? '—' : averageResponseTime(emergencies) },
  ]

  return (
    <Layout>
      <div className="px-8 py-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-semibold text-slate-50">Dashboard</h2>
            <p className="text-sm text-slate-500 mt-0.5">
              Welcome back, {user?.full_name?.split(' ')[0]}. Signed in as{' '}
              <span className="font-mono text-slate-400">{user?.role}</span>.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {stats.map((stat) => (
            <div key={stat.label} className="panel p-4">
              <p className="text-xs text-slate-500">{stat.label}</p>
              <p className="text-2xl font-display font-semibold text-slate-100 mt-1">{stat.value}</p>
            </div>
          ))}
        </div>

        <div className="panel p-5 mb-6">
          <h3 className="text-sm font-medium text-slate-200 mb-3">Recent emergencies</h3>
          {isLoading && <p className="text-sm text-slate-500">Loading…</p>}
          {!isLoading && recentEmergencies.length === 0 && (
            <p className="text-sm text-slate-500">
              None yet. Head to Sensor Monitor to run a fall simulation and see one land here.
            </p>
          )}
          <div className="space-y-2">
            {recentEmergencies.map((e) => (
              <div key={e.id} className="flex items-center justify-between text-sm">
                <span className="text-slate-300">{e.event_type.replace(/_/g, ' ')}</span>
                <span className="text-xs text-slate-500 font-mono">{e.severity} · {e.status}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="panel p-6">
          <h3 className="text-sm font-medium text-slate-200 mb-2">Project status</h3>
          <p className="text-sm text-slate-400 leading-relaxed">
            Phases 1–3 are live: authentication, people/devices, the sensor simulator, fall detection, the
            Emergency Engine, real email notifications, escalation, and acknowledge/resolve/false-alarm
            handling — all wired to the real backend.
          </p>
          <p className="text-sm text-slate-500 mt-3">
            <strong className="text-slate-400">Not implemented yet:</strong> Video Analysis (traffic
            accident / fire detection), Analytics, and Settings. These land in Phases 4–5.
          </p>
        </div>
      </div>
    </Layout>
  )
}
