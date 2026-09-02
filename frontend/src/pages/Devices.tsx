import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { createDevice, listDevices, listPeople, type Device, type Person } from '../services/api'
import { Layout } from '../components/Layout'

function timeAgo(iso: string | null): string {
  if (!iso) return 'Never'
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (seconds < 60) return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  return `${Math.floor(seconds / 3600)}h ago`
}

export function Devices() {
  const [devices, setDevices] = useState<Device[]>([])
  const [people, setPeople] = useState<Person[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [deviceName, setDeviceName] = useState('')
  const [personId, setPersonId] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const load = async () => {
    setIsLoading(true)
    try {
      const [d, p] = await Promise.all([listDevices(), listPeople()])
      setDevices(d)
      setPeople(p)
      if (p.length > 0 && !personId) setPersonId(p[0].id)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const personName = (id: string) => people.find((p) => p.id === id)?.name ?? 'Unknown'

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await createDevice(deviceName, personId)
      setDeviceName('')
      setShowForm(false)
      await load()
    } catch {
      setError('Could not create device. Make sure a person is selected.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Layout>
      <div className="px-8 py-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-semibold text-slate-50">Devices</h2>
            <p className="text-sm text-slate-500 mt-0.5">
              Software Sensor Simulator instances attached to a monitored person.
            </p>
          </div>
          <button
            onClick={() => setShowForm((v) => !v)}
            disabled={people.length === 0}
            className="bg-accent hover:bg-accent/90 disabled:opacity-40 text-white text-sm font-medium rounded-md px-4 py-2 transition-colors"
          >
            {showForm ? 'Cancel' : '+ Add device'}
          </button>
        </div>

        {people.length === 0 && !isLoading && (
          <div className="panel p-6 text-sm text-slate-500 mb-6">
            No people added yet. <Link to="/people" className="text-accent hover:underline">Add a person first</Link>{' '}
            before attaching a device.
          </div>
        )}

        {showForm && (
          <form onSubmit={handleCreate} className="panel p-5 mb-6 space-y-4 max-w-lg">
            <div>
              <label className="block text-xs text-slate-400 mb-1.5">Device name</label>
              <input
                required
                value={deviceName}
                onChange={(e) => setDeviceName(e.target.value)}
                className="w-full rounded-md bg-ink-800 border border-ink-700 px-3 py-2 text-sm text-slate-100 focus:border-accent focus:outline-none"
                placeholder="Grandfather Watch"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1.5">Assigned to</label>
              <select
                value={personId}
                onChange={(e) => setPersonId(e.target.value)}
                className="w-full rounded-md bg-ink-800 border border-ink-700 px-3 py-2 text-sm text-slate-100 focus:border-accent focus:outline-none"
              >
                {people.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>

            {error && (
              <p className="text-xs text-signal-critical bg-signal-critical/10 border border-signal-critical/30 rounded-md px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className="bg-accent hover:bg-accent/90 disabled:opacity-50 text-white text-sm font-medium rounded-md px-4 py-2 transition-colors"
            >
              {isSubmitting ? 'Creating…' : 'Create device'}
            </button>
          </form>
        )}

        {isLoading ? (
          <p className="text-sm text-slate-500">Loading…</p>
        ) : devices.length === 0 ? (
          <div className="panel p-6 text-sm text-slate-500">No devices yet.</div>
        ) : (
          <div className="panel divide-y divide-ink-700">
            {devices.map((d) => (
              <div key={d.id} className="px-5 py-4 flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-100">{d.device_name}</p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {personName(d.person_id)} · {d.device_type} · last seen {timeAgo(d.last_seen)}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-slate-500 font-mono">{d.battery_level.toFixed(0)}%</span>
                  <span
                    className={`flex items-center gap-1.5 text-xs font-mono ${
                      d.status === 'ONLINE' ? 'text-signal-normal' : 'text-slate-500'
                    }`}
                  >
                    <span className={`status-dot ${d.status === 'ONLINE' ? 'bg-signal-normal' : 'bg-slate-600'}`} />
                    {d.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Layout>
  )
}
