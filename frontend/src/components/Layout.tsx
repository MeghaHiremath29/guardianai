import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const NAV_ITEMS: { label: string; path: string; phase: number | null }[] = [
  { label: 'Dashboard', path: '/', phase: null },
  { label: 'Live Emergencies', path: '/emergencies', phase: null },
  { label: 'Sensor Monitor', path: '/sensors', phase: null },
  { label: 'Video Analysis', path: '/videos', phase: null },
  { label: 'Devices', path: '/devices', phase: null },
  { label: 'People', path: '/people', phase: null },
  { label: 'Notifications', path: '/notifications', phase: null },
  { label: 'Emergency History', path: '/history', phase: null },
  { label: 'Analytics', path: '/analytics', phase: 5 },
  { label: 'Settings', path: '/settings', phase: 5 },
]

export function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth()

  return (
    <div className="min-h-screen flex bg-ink-950">
      <aside className="w-60 shrink-0 border-r border-ink-700 bg-ink-900 flex flex-col">
        <div className="px-5 py-5 border-b border-ink-700">
          <div className="flex items-center gap-2">
            <span className="status-dot bg-signal-normal" />
            <h1 className="text-base font-semibold tracking-tight">GuardianAI</h1>
          </div>
          <p className="text-xs text-slate-500 mt-1 font-mono">Emergency Ops Console</p>
        </div>

        <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) =>
                `flex items-center justify-between px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive
                    ? 'bg-ink-800 text-slate-50'
                    : 'text-slate-400 hover:bg-ink-800/60 hover:text-slate-200'
                }`
              }
            >
              <span>{item.label}</span>
              {item.phase && (
                <span className="text-[10px] font-mono text-slate-600 border border-ink-700 rounded px-1.5 py-0.5">
                  P{item.phase}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="px-4 py-4 border-t border-ink-700">
          <p className="text-sm text-slate-200 truncate">{user?.full_name}</p>
          <p className="text-xs text-slate-500 truncate">{user?.role}</p>
          <button
            onClick={logout}
            className="mt-3 text-xs text-slate-400 hover:text-slate-200 border border-ink-700 rounded px-2 py-1 transition-colors"
          >
            Sign out
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  )
}
