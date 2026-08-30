import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { isAxiosError } from 'axios'
import { register, type UserRole } from '../services/api'
import { useAuth } from '../context/AuthContext'

const ROLES: UserRole[] = ['CARETAKER', 'FAMILY', 'DOCTOR', 'ADMIN']

export function Register() {
  const { login } = useAuth()
  const navigate = useNavigate()

  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<UserRole>('FAMILY')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await register(fullName, email, password, role)
      await login(email, password)
      navigate('/')
    } catch (err) {
      if (isAxiosError(err) && err.response?.status === 409) {
        setError('An account with this email already exists.')
      } else if (isAxiosError(err) && err.response?.status === 422) {
        setError('Please check your details — password needs at least 8 characters.')
      } else {
        setError('Something went wrong. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-ink-950 px-4">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-2 justify-center mb-8">
          <span className="status-dot bg-signal-normal" />
          <h1 className="text-lg font-semibold tracking-tight text-slate-50">GuardianAI</h1>
        </div>

        <div className="panel p-6">
          <h2 className="text-sm font-medium text-slate-300 mb-1">Create an account</h2>
          <p className="text-xs text-slate-500 mb-5">Demo project — pick the role you want to test with</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="fullName" className="block text-xs text-slate-400 mb-1.5">Full name</label>
              <input
                id="fullName"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="w-full rounded-md bg-ink-800 border border-ink-700 px-3 py-2 text-sm text-slate-100 focus:border-accent focus:outline-none"
                placeholder="Jane Doe"
              />
            </div>

            <div>
              <label htmlFor="email" className="block text-xs text-slate-400 mb-1.5">Email</label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-md bg-ink-800 border border-ink-700 px-3 py-2 text-sm text-slate-100 focus:border-accent focus:outline-none"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-xs text-slate-400 mb-1.5">Password</label>
              <input
                id="password"
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-md bg-ink-800 border border-ink-700 px-3 py-2 text-sm text-slate-100 focus:border-accent focus:outline-none"
                placeholder="At least 8 characters"
              />
            </div>

            <div>
              <label htmlFor="role" className="block text-xs text-slate-400 mb-1.5">Role</label>
              <select
                id="role"
                value={role}
                onChange={(e) => setRole(e.target.value as UserRole)}
                className="w-full rounded-md bg-ink-800 border border-ink-700 px-3 py-2 text-sm text-slate-100 focus:border-accent focus:outline-none"
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>{r}</option>
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
              className="w-full bg-accent hover:bg-accent/90 disabled:opacity-50 text-white text-sm font-medium rounded-md px-3 py-2.5 transition-colors"
            >
              {isSubmitting ? 'Creating account…' : 'Create account'}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-slate-500 mt-4">
          Already have an account? <Link to="/login" className="text-accent hover:underline">Sign in</Link>
        </p>
      </div>
    </div>
  )
}
