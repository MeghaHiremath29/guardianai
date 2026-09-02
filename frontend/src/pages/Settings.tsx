import { useEffect, useState } from 'react'
import { isAxiosError } from 'axios'
import { Layout } from '../components/Layout'
import { useAuth } from '../context/AuthContext'
import { getSystemConfig, listAuditLogs, type AuditLogEntry, type SystemConfig } from '../services/api'

const ACTION_LABELS: Record<string, string> = {
  USER_REGISTERED: 'User registered',
  USER_LOGIN: 'User logged in',
  USER_LOGIN_FAILED: 'Failed login attempt',
  PERSON_CREATED: 'Person created',
  DEVICE_CREATED: 'Device created',
  EMERGENCY_CREATED: 'Emergency created',
  EMERGENCY_ACKNOWLEDGED: 'Emergency acknowledged',
  EMERGENCY_RESOLVED: 'Emergency resolved',
  EMERGENCY_FALSE_ALARM: 'Marked false alarm',
  VIDEO_UPLOADED: 'Video/image uploaded',
  NOTIFICATION_TEST_SENT: 'Test notification sent',
}

function ConfigRow({ label, value }: { label: string; value: string | number | boolean }) {
  return (
    <div className="flex items-center justify-between py-1.5 text-sm">
      <span className="text-slate-400">{label}</span>
      <span className="text-slate-200 font-mono text-xs">{String(value)}</span>
    </div>
  )
}

export function Settings() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'ADMIN'

  const [config, setConfig] = useState<SystemConfig | null>(null)
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(isAdmin)

  useEffect(() => {
    if (!isAdmin) return
    Promise.all([getSystemConfig(), listAuditLogs(100)])
      .then(([c, l]) => {
        setConfig(c)
        setLogs(l)
      })
      .catch((err) => {
        if (isAxiosError(err) && err.response?.status === 403) {
          setError('Admin access required.')
        } else {
          setError('Could not load settings.')
        }
      })
      .finally(() => setIsLoading(false))
  }, [isAdmin])

  return (
    <Layout>
      <div className="px-8 py-6">
        <h2 className="text-xl font-semibold text-slate-50">Settings</h2>
        <p className="text-sm text-slate-500 mt-0.5 mb-6">
          System configuration and the audit trail — admin only.
        </p>

        {!isAdmin && (
          <div className="panel p-6">
            <p className="text-sm text-slate-400">
              Settings are only visible to ADMIN accounts. You're signed in as{' '}
              <span className="font-mono text-slate-300">{user?.role}</span>.
            </p>
          </div>
        )}

        {isAdmin && isLoading && <p className="text-sm text-slate-500">Loading…</p>}
        {isAdmin && error && (
          <p className="text-sm text-signal-critical bg-signal-critical/10 border border-signal-critical/30 rounded-md px-3 py-2">
            {error}
          </p>
        )}

        {isAdmin && config && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            <div className="panel p-5">
              <h3 className="text-sm font-medium text-slate-200 mb-1">Fall-detection risk engine</h3>
              <p className="text-xs text-slate-500 mb-3">
                Live values from the running backend. Read-only — see the note below.
              </p>
              <div className="divide-y divide-ink-700">
                <ConfigRow label="Acceleration spike score" value={config.fall_detection.acceleration_spike_score} />
                <ConfigRow label="Orientation change score" value={config.fall_detection.orientation_change_score} />
                <ConfigRow label="Inactivity max score" value={config.fall_detection.inactivity_max_score} />
                <ConfigRow label="Abnormal heart rate score" value={config.fall_detection.abnormal_heart_rate_score} />
                <ConfigRow label="CRITICAL threshold" value={`≥ ${config.fall_detection.critical_threshold}`} />
                <ConfigRow label="HIGH threshold" value={`≥ ${config.fall_detection.high_threshold}`} />
                <ConfigRow label="WARNING threshold" value={`≥ ${config.fall_detection.warning_threshold}`} />
              </div>
            </div>

            <div className="panel p-5">
              <h3 className="text-sm font-medium text-slate-200 mb-1">Escalation & system</h3>
              <p className="text-xs text-slate-500 mb-3">Timings and integration status.</p>
              <div className="divide-y divide-ink-700">
                <ConfigRow label="Step 1 delay (→ family)" value={`${config.escalation.step1_delay_seconds}s`} />
                <ConfigRow label="Step 2 delay (→ doctor, CRITICAL only)" value={`${config.escalation.step2_delay_seconds}s`} />
                <ConfigRow label="Scheduler check interval" value={`${config.escalation.check_interval_seconds}s`} />
                <ConfigRow label="Max upload size" value={`${config.uploads.max_upload_size_mb} MB`} />
                <ConfigRow label="SMTP configured" value={config.notifications.smtp_configured} />
                <ConfigRow label="Telegram configured" value={config.notifications.telegram_configured} />
              </div>
              <p className="text-xs text-slate-600 mt-3 leading-relaxed">{config.editable_note}</p>
            </div>
          </div>
        )}

        {isAdmin && (
          <div className="panel p-5">
            <h3 className="text-sm font-medium text-slate-200 mb-1">Audit log</h3>
            <p className="text-xs text-slate-500 mb-3">Most recent 100 system-wide actions.</p>
            <div className="divide-y divide-ink-700 max-h-96 overflow-y-auto">
              {logs.length === 0 && <p className="text-xs text-slate-500 py-2">No activity logged yet.</p>}
              {logs.map((entry) => (
                <div key={entry.id} className="py-2 flex items-center justify-between text-sm">
                  <div>
                    <span className="text-slate-200">{ACTION_LABELS[entry.action] ?? entry.action}</span>
                    {entry.actor_email && <span className="text-slate-500 text-xs"> — {entry.actor_email}</span>}
                    {entry.detail && <span className="text-slate-600 text-xs"> ({entry.detail})</span>}
                  </div>
                  <span className="text-xs text-slate-600 font-mono shrink-0 ml-4">
                    {new Date(entry.created_at + 'Z').toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}
