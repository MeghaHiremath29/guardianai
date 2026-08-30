import { useEffect, useState, type FormEvent } from 'react'
import { isAxiosError } from 'axios'
import { Layout } from '../components/Layout'
import { createPerson, listPeople, type Person } from '../services/api'

export function People() {
  const [people, setPeople] = useState<Person[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [name, setName] = useState('')
  const [age, setAge] = useState('')
  const [address, setAddress] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const load = async () => {
    setIsLoading(true)
    try {
      setPeople(await listPeople())
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await createPerson({
        name,
        age: age ? Number(age) : undefined,
        address: address || undefined,
      })
      setName('')
      setAge('')
      setAddress('')
      setShowForm(false)
      await load()
    } catch (err) {
      if (isAxiosError(err) && err.response?.status === 403) {
        setError('Only ADMIN or CARETAKER accounts can add a monitored person.')
      } else {
        setError('Could not create person. Please check the details and try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Layout>
      <div className="px-8 py-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-semibold text-slate-50">People</h2>
            <p className="text-sm text-slate-500 mt-0.5">Individuals being monitored by GuardianAI.</p>
          </div>
          <button
            onClick={() => setShowForm((v) => !v)}
            className="bg-accent hover:bg-accent/90 text-white text-sm font-medium rounded-md px-4 py-2 transition-colors"
          >
            {showForm ? 'Cancel' : '+ Add person'}
          </button>
        </div>

        {showForm && (
          <form onSubmit={handleCreate} className="panel p-5 mb-6 space-y-4 max-w-lg">
            <div>
              <label className="block text-xs text-slate-400 mb-1.5">Name</label>
              <input
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full rounded-md bg-ink-800 border border-ink-700 px-3 py-2 text-sm text-slate-100 focus:border-accent focus:outline-none"
                placeholder="Grandfather Rao"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-slate-400 mb-1.5">Age</label>
                <input
                  type="number"
                  min={0}
                  max={130}
                  value={age}
                  onChange={(e) => setAge(e.target.value)}
                  className="w-full rounded-md bg-ink-800 border border-ink-700 px-3 py-2 text-sm text-slate-100 focus:border-accent focus:outline-none"
                  placeholder="78"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1.5">Address</label>
                <input
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  className="w-full rounded-md bg-ink-800 border border-ink-700 px-3 py-2 text-sm text-slate-100 focus:border-accent focus:outline-none"
                  placeholder="12 MG Road, Bengaluru"
                />
              </div>
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
              {isSubmitting ? 'Creating…' : 'Create person'}
            </button>
          </form>
        )}

        {isLoading ? (
          <p className="text-sm text-slate-500">Loading…</p>
        ) : people.length === 0 ? (
          <div className="panel p-6 text-sm text-slate-500">
            No one has been added yet. Add a person to attach a device and start the sensor simulator.
          </div>
        ) : (
          <div className="panel divide-y divide-ink-700">
            {people.map((p) => (
              <div key={p.id} className="px-5 py-4 flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-100">{p.name}</p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {p.age ? `${p.age} years old` : 'Age not set'}
                    {p.address ? ` · ${p.address}` : ''}
                  </p>
                </div>
                <span className="text-[10px] font-mono text-slate-600 border border-ink-700 rounded px-2 py-1">
                  {p.emergency_contacts.length} contact{p.emergency_contacts.length === 1 ? '' : 's'}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </Layout>
  )
}
