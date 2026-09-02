import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  getReadingHistory,
  listDevices,
  listPeople,
  runSimulation,
  type Device,
  type DetectionResultOut,
  type Person,
  type Scenario,
  type SensorReadingOut,
} from '../services/api'
import { Layout } from '../components/Layout'

const SCENARIOS: { value: Scenario; label: string; description: string }[] = [
  { value: 'NORMAL', label: 'Normal activity', description: 'Baseline vitals, no risk signals' },
  { value: 'WALKING', label: 'Walking', description: 'Elevated heart rate and motion, still normal' },
  { value: 'FALL', label: 'Fall', description: 'Impact spike + lying orientation + stillness' },
  { value: 'FALL_HIGH_HEART_RATE', label: 'Fall + high heart rate', description: 'Fall plus a stress heart-rate response' },
  { value: 'INACTIVITY_AFTER_FALL', label: 'Inactivity after fall', description: 'Modest impact, severity builds from prolonged stillness' },
]

const SEVERITY_COLOR: Record<string, string> = {
  NORMAL: 'text-signal-normal',
  WARNING: 'text-signal-warning',
  HIGH: 'text-signal-high',
  CRITICAL: 'text-signal-critical',
}

export function SensorMonitor() {
  const [devices, setDevices] = useState<Device[]>([])
  const [people, setPeople] = useState<Person[]>([])
  const [selectedDeviceId, setSelectedDeviceId] = useState('')
  const [scenario, setScenario] = useState<Scenario>('FALL')
  const [isRunning, setIsRunning] = useState(false)
  const [result, setResult] = useState<DetectionResultOut | null>(null)
  const [history, setHistory] = useState<SensorReadingOut[]>([])
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    const [d, p] = await Promise.all([listDevices(), listPeople()])
    setDevices(d)
    setPeople(p)
    if (d.length > 0 && !selectedDeviceId) setSelectedDeviceId(d[0].id)
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const personName = (id: string) => people.find((p) => p.id === id)?.name ?? 'Unknown'
  const selectedDevice = devices.find((d) => d.id === selectedDeviceId)

  const handleRun = async () => {
    if (!selectedDeviceId) return
    setError(null)
    setIsRunning(true)
    setResult(null)
    try {
      const res = await runSimulation(selectedDeviceId, scenario, 20)
      setResult(res)
      setHistory(await getReadingHistory(selectedDeviceId, 30))
    } catch {
      setError('Simulation failed. Is the backend running?')
    } finally {
      setIsRunning(false)
    }
  }

  return (
    <Layout>
      <div className="px-8 py-6">
        <div className="mb-6">
          <h2 className="text-xl font-semibold text-slate-50">Sensor Monitor</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Software Sensor Simulator — generates real sensor readings sent through the live API, evaluated by
            the actual fall-detection engine. Nothing here is a hard-coded result.
          </p>
        </div>

        {devices.length === 0 ? (
          <div className="panel p-6 text-sm text-slate-500">
            No devices yet. <Link to="/devices" className="text-accent hover:underline">Add a device</Link> to
            run the simulator.
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="panel p-5 lg:col-span-1 space-y-4 h-fit">
              <div>
                <label className="block text-xs text-slate-400 mb-1.5">Device</label>
                <select
                  value={selectedDeviceId}
                  onChange={(e) => { setSelectedDeviceId(e.target.value); setResult(null); setHistory([]) }}
                  className="w-full rounded-md bg-ink-800 border border-ink-700 px-3 py-2 text-sm text-slate-100 focus:border-accent focus:outline-none"
                >
                  {devices.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.device_name} — {personName(d.person_id)}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs text-slate-400 mb-1.5">Scenario</label>
                <div className="space-y-1.5">
                  {SCENARIOS.map((s) => (
                    <label
                      key={s.value}
                      className={`flex flex-col gap-0.5 px-3 py-2 rounded-md border cursor-pointer transition-colors ${
                        scenario === s.value
                          ? 'border-accent bg-accent/10'
                          : 'border-ink-700 hover:bg-ink-800/60'
                      }`}
                    >
                      <span className="flex items-center gap-2 text-sm text-slate-200">
                        <input
                          type="radio"
                          name="scenario"
                          checked={scenario === s.value}
                          onChange={() => setScenario(s.value)}
                          className="accent-accent"
                        />
                        {s.label}
                      </span>
                      <span className="text-xs text-slate-500 pl-5">{s.description}</span>
                    </label>
                  ))}
                </div>
              </div>

              <button
                onClick={handleRun}
                disabled={isRunning}
                className="w-full bg-accent hover:bg-accent/90 disabled:opacity-50 text-white text-sm font-medium rounded-md px-4 py-2.5 transition-colors"
              >
                {isRunning ? 'Running simulation…' : 'Run scenario'}
              </button>

              {selectedDevice && (
                <p className="text-xs text-slate-500 pt-1">
                  Status:{' '}
                  <span className={selectedDevice.status === 'ONLINE' ? 'text-signal-normal' : 'text-slate-500'}>
                    {selectedDevice.status}
                  </span>
                </p>
              )}
            </div>

            <div className="lg:col-span-2 space-y-6">
              {error && (
                <div className="panel p-4 border-signal-critical/30 text-sm text-signal-critical bg-signal-critical/10">
                  {error}
                </div>
              )}

              {result ? (
                <div className="panel p-5">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-medium text-slate-200">Detection result</h3>
                    <span className={`text-sm font-mono font-semibold ${SEVERITY_COLOR[result.severity]}`}>
                      {result.severity}
                    </span>
                  </div>
                  <p className="text-sm text-slate-300 mb-1">
                    {result.event_type === 'NORMAL'
                      ? 'No emergency signals detected.'
                      : `Possible ${result.event_type.replace('_', ' ').toLowerCase()} detected`}
                    {' — '}confidence {(result.confidence * 100).toFixed(0)}%
                  </p>
                  {result.reasons.length > 0 && (
                    <ul className="text-sm text-slate-400 list-disc list-inside mt-2 space-y-0.5">
                      {result.reasons.map((r) => <li key={r}>{r}</li>)}
                    </ul>
                  )}
                  {result.emergency_created && (
                    <div className="mt-4 pt-4 border-t border-ink-700">
                      <p className="text-sm text-signal-critical font-medium">
                        Emergency created — see Live Emergencies (Phase 3).
                      </p>
                      <p className="text-xs text-slate-600 mt-1 font-mono">{result.emergency_id}</p>
                    </div>
                  )}
                  <p className="text-xs text-slate-600 mt-4">
                    This is a software risk estimate, not a medical diagnosis.
                  </p>
                </div>
              ) : (
                <div className="panel p-6 text-sm text-slate-500">
                  Select a scenario and run it to see a live detection result from the real fall-detection engine.
                </div>
              )}

              {history.length > 0 && (
                <div className="panel p-5">
                  <h3 className="text-sm font-medium text-slate-200 mb-3">
                    Recent readings ({history.length})
                  </h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="text-slate-500 text-left border-b border-ink-700">
                          <th className="pb-2 pr-4 font-normal">Time</th>
                          <th className="pb-2 pr-4 font-normal">HR</th>
                          <th className="pb-2 pr-4 font-normal">Accel</th>
                          <th className="pb-2 pr-4 font-normal">Orientation</th>
                          <th className="pb-2 font-normal">Inactivity</th>
                        </tr>
                      </thead>
                      <tbody className="font-mono text-slate-400">
                        {history.slice(-10).map((r) => (
                          <tr key={r.id} className="border-b border-ink-800/60">
                            <td className="py-1.5 pr-4">{new Date(r.timestamp).toLocaleTimeString()}</td>
                            <td className="py-1.5 pr-4">{r.heart_rate?.toFixed(0) ?? '—'}</td>
                            <td className="py-1.5 pr-4">{r.accel_magnitude.toFixed(2)}g</td>
                            <td className="py-1.5 pr-4">{r.orientation}</td>
                            <td className="py-1.5">{r.inactivity_duration.toFixed(1)}s</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}
