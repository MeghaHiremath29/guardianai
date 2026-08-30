import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { isAxiosError } from 'axios'
import { useAuth } from '../context/AuthContext'

export function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await login(email, password)
      navigate('/')
    } catch (err) {
      if (isAxiosError(err) && err.response?.status === 401) {
        setError('Incorrect email or password.')
      } else if (isAxiosError(err) && err.code === 'ERR_NETWORK') {
        setError('Cannot reach the GuardianAI backend. Is it running on localhost:8000?')
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
          <h2 className="text-sm font-medium text-slate-300 mb-1">Sign in to the console</h2>
          <p className="text-xs text-slate-500 mb-5">Emergency detection & response system</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-xs text-slate-400 mb-1.5">
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-md bg-ink-800 border border-ink-700 px-3 py-2 text-sm text-slate-100 focus:border-accent focus:outline-none"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-xs text-slate-400 mb-1.5">
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-md bg-ink-800 border border-ink-700 px-3 py-2 text-sm text-slate-100 focus:border-accent focus:outline-none"
                placeholder="••••••••"
              />
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
              {isSubmitting ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-slate-500 mt-4">
          No account? <Link to="/register" className="text-accent hover:underline">Register</Link>
        </p>
      </div>
    </div>
  )
}
