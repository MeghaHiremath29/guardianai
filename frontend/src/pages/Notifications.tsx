import { useEffect, useState, type FormEvent } from 'react'
import { isAxiosError } from 'axios'
import { Layout } from '../components/Layout'
import { useAuth } from '../context/AuthContext'
import {
  listNotifications,
  sendTestNotification,
  type NotificationDeliveryStatus,
  type NotificationOut,
} from '../services/api'

const STATUS_STYLES: Record<NotificationDeliveryStatus, string> = {
  SENT: 'text-signal-normal',
  FAILED: 'text-signal-critical',
  SKIPPED: 'text-signal-warning',
}

export function Notifications() {
  const { user } = useAuth()
  const [notifications, setNotifications] = useState<NotificationOut[]>([])
  const [isLoading, setIsLoading] = useState(true)

  const [testEmail, setTestEmail] = useState('')
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null)
  const [testPending, setTestPending] = useState(false)

  useEffect(() => {
    listNotifications().then((data) => {
      setNotifications(data)
      setIsLoading(false)
    })
  }, [])

  const handleTest = async (e: FormEvent) => {
    e.preventDefault()
    setTestPending(true)
    setTestResult(null)
    try {
      const result = await sendTestNotification(testEmail)
      setTestResult({ ok: true, message: result.detail })
    } catch (err) {
      if (isAxiosError(err) && err.response?.status === 502) {
        setTestResult({ ok: false, message: err.response.data?.detail ?? 'SMTP send failed.' })
      } else if (isAxiosError(err) && err.response?.status === 403) {
        setTestResult({ ok: false, message: 'Only an admin can send a test notification.' })
      } else {
        setTestResult({ ok: false, message: 'Something went wrong.' })
      }
    } finally {
      setTestPending(false)
    }
  }

  return (
    <Layout>
      <div className="px-8 py-6">
        <h2 className="text-xl font-semibold text-slate-50">Notifications</h2>
        <p className="text-sm text-slate-500 mt-0.5 mb-6">
          Every attempt is logged here — including failed and skipped ones. Nothing is marked "sent"
          unless the email actually went out.
        </p>

        {user?.role === 'ADMIN' && (
          <div className="panel p-5 mb-6 max-w-md">
            <h3 className="text-sm font-medium text-slate-200 mb-1">Test SMTP configuration</h3>
            <p className="text-xs text-slate-500 mb-3">
              Sends a real email through the SMTP settings in backend/.env.
            </p>
            <form onSubmit={handleTest} className="flex gap-2">
              <input
                type="email"
                required
                value={testEmail}
                onChange={(e) => setTestEmail(e.target.value)}
                placeholder="you@example.com"
                className="flex-1 rounded-md bg-ink-800 border border-ink-700 px-3 py-2 text-sm text-slate-100 focus:border-accent focus:outline-none"
              />
              <button
                type="submit"
                disabled={testPending}
                className="text-xs bg-accent hover:bg-accent/90 disabled:opacity-50 text-white rounded-md px-3 py-2 transition-colors whitespace-nowrap"
              >
                {testPending ? 'Sending…' : 'Send test'}
              </button>
            </form>
            {testResult && (
              <p className={`mt-3 text-xs ${testResult.ok ? 'text-signal-normal' : 'text-signal-critical'}`}>
                {testResult.message}
              </p>
            )}
          </div>
        )}

        <div className="panel divide-y divide-ink-700">
          {isLoading && <p className="p-4 text-sm text-slate-500">Loading…</p>}
          {!isLoading && notifications.length === 0 && (
            <p className="p-4 text-sm text-slate-500">
              No notifications yet — they're created automatically when an emergency is detected.
            </p>
          )}
          {notifications.map((n) => (
            <div key={n.id} className="px-4 py-3 flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-200">
                  {n.recipient_role.charAt(0) + n.recipient_role.slice(1).toLowerCase()}
                  {n.recipient_name ? ` — ${n.recipient_name}` : ''}
                  <span className="text-slate-600"> via {n.channel.toLowerCase()}</span>
                </p>
                <p className="text-xs text-slate-500 mt-0.5">{n.detail}</p>
              </div>
              <span className={`text-xs font-mono uppercase shrink-0 ml-4 ${STATUS_STYLES[n.status]}`}>
                {n.status}
              </span>
            </div>
          ))}
        </div>
      </div>
    </Layout>
  )
}
