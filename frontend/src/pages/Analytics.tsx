import { useEffect, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Layout } from '../components/Layout'
import {
  getAnalyticsSummary,
  getAnalyticsTrends,
  getDeviceUptime,
  type AnalyticsSummary,
  type AnalyticsTrends,
  type DeviceUptimeItem,
} from '../services/api'

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: '#C0392B',
  HIGH: '#C0602E',
  WARNING: '#C08A2E',
  NORMAL: '#2E7D6B',
}

function formatSeconds(seconds: number | null): string {
  if (seconds === null) return '—'
  if (seconds < 60) return `${Math.round(seconds)}s`
  return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`
}

const chartTooltipStyle = {
  background: '#111A2E',
  border: '1px solid #26365A',
  borderRadius: 6,
  fontSize: 12,
}

export function Analytics() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null)
  const [trends, setTrends] = useState<AnalyticsTrends | null>(null)
  const [devices, setDevices] = useState<DeviceUptimeItem[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    Promise.all([getAnalyticsSummary(), getAnalyticsTrends(14), getDeviceUptime()]).then(
      ([s, t, d]) => {
        setSummary(s)
        setTrends(t)
        setDevices(d)
        setIsLoading(false)
      },
    )
  }, [])

  const hasAnyData = summary && summary.total_emergencies > 0

  return (
    <Layout>
      <div className="px-8 py-6">
        <h2 className="text-xl font-semibold text-slate-50">Analytics</h2>
        <p className="text-sm text-slate-500 mt-0.5 mb-6">
          Computed live from the database — nothing here is precomputed or sample data.
        </p>

        {isLoading && <p className="text-sm text-slate-500">Loading…</p>}

        {!isLoading && !hasAnyData && (
          <div className="panel p-6 mb-6">
            <p className="text-sm text-slate-400">
              No emergencies recorded yet, so there's nothing to chart. Run a fall simulation from Sensor
              Monitor, or upload footage from Video Analysis, to see real numbers here.
            </p>
          </div>
        )}

        {!isLoading && summary && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div className="panel p-4">
                <p className="text-xs text-slate-500">Total emergencies</p>
                <p className="text-2xl font-display font-semibold text-slate-100 mt-1">{summary.total_emergencies}</p>
              </div>
              <div className="panel p-4">
                <p className="text-xs text-slate-500">False alarm rate</p>
                <p className="text-2xl font-display font-semibold text-slate-100 mt-1">
                  {Math.round(summary.false_alarm_rate * 100)}%
                </p>
              </div>
              <div className="panel p-4">
                <p className="text-xs text-slate-500">Avg. acknowledgement</p>
                <p className="text-2xl font-display font-semibold text-slate-100 mt-1">
                  {formatSeconds(summary.avg_acknowledgement_seconds)}
                </p>
              </div>
              <div className="panel p-4">
                <p className="text-xs text-slate-500">Avg. resolution time</p>
                <p className="text-2xl font-display font-semibold text-slate-100 mt-1">
                  {formatSeconds(summary.avg_response_seconds)}
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
              <div className="panel p-5">
                <h3 className="text-sm font-medium text-slate-200 mb-1">Status breakdown</h3>
                <p className="text-xs text-slate-500 mb-4">Current state of every emergency ever recorded</p>
                {hasAnyData ? (
                  <ResponsiveContainer width="100%" height={180}>
                    <BarChart
                      data={[
                        { name: 'Open', value: summary.open_count },
                        { name: 'Acked', value: summary.acknowledged_count },
                        { name: 'Resolved', value: summary.resolved_count },
                        { name: 'False alarm', value: summary.false_alarm_count },
                      ]}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#26365A" vertical={false} />
                      <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#8494B0' }} axisLine={{ stroke: '#26365A' }} tickLine={false} />
                      <YAxis tick={{ fontSize: 11, fill: '#8494B0' }} axisLine={false} tickLine={false} allowDecimals={false} />
                      <Tooltip contentStyle={chartTooltipStyle} labelStyle={{ color: '#E2E8F0' }} />
                      <Bar dataKey="value" fill="#3E7CB8" radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="text-xs text-slate-500">No data yet</p>
                )}
              </div>

              <div className="panel p-5">
                <h3 className="text-sm font-medium text-slate-200 mb-1">Severity distribution</h3>
                <p className="text-xs text-slate-500 mb-4">All emergencies, by AI-assessed severity</p>
                {trends && trends.by_severity.length > 0 ? (
                  <ResponsiveContainer width="100%" height={180}>
                    <BarChart data={trends.by_severity.map((s) => ({ name: s.severity, value: s.count }))}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#26365A" vertical={false} />
                      <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#8494B0' }} axisLine={{ stroke: '#26365A' }} tickLine={false} />
                      <YAxis tick={{ fontSize: 11, fill: '#8494B0' }} axisLine={false} tickLine={false} allowDecimals={false} />
                      <Tooltip contentStyle={chartTooltipStyle} labelStyle={{ color: '#E2E8F0' }} />
                      <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                        {trends.by_severity.map((s) => (
                          <Cell key={s.severity} fill={SEVERITY_COLORS[s.severity] ?? '#3E7CB8'} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="text-xs text-slate-500">No data yet</p>
                )}
              </div>
            </div>

            <div className="panel p-5 mb-6">
              <h3 className="text-sm font-medium text-slate-200 mb-1">Emergency trend (last 14 days)</h3>
              <p className="text-xs text-slate-500 mb-4">Emergencies created per day</p>
              {trends && (
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={trends.daily_counts}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#26365A" vertical={false} />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 10, fill: '#8494B0' }}
                      axisLine={{ stroke: '#26365A' }}
                      tickLine={false}
                      tickFormatter={(d: string) => d.slice(5)}
                    />
                    <YAxis tick={{ fontSize: 11, fill: '#8494B0' }} axisLine={false} tickLine={false} allowDecimals={false} />
                    <Tooltip contentStyle={chartTooltipStyle} labelStyle={{ color: '#E2E8F0' }} />
                    <Line type="monotone" dataKey="count" stroke="#3E7CB8" strokeWidth={2} dot={{ r: 3, fill: '#3E7CB8' }} />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>

            <div className="panel p-5">
              <h3 className="text-sm font-medium text-slate-200 mb-3">Device uptime</h3>
              {devices.length === 0 && <p className="text-xs text-slate-500">No devices registered yet.</p>}
              <div className="divide-y divide-ink-700">
                {devices.map((d) => (
                  <div key={d.device_id} className="flex items-center justify-between py-2 text-sm">
                    <div className="flex items-center gap-2">
                      <span className={`status-dot ${d.status === 'ONLINE' ? 'bg-signal-normal' : 'bg-slate-600'}`} />
                      <span className="text-slate-200">{d.device_name}</span>
                    </div>
                    <div className="text-xs text-slate-500 font-mono">
                      {Math.round(d.battery_level)}% battery
                      {d.last_seen && ` · last seen ${new Date(d.last_seen).toLocaleTimeString()}`}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </Layout>
  )
}
