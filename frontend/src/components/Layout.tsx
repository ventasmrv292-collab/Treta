import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import {
  LayoutDashboard,
  PlusCircle,
  History,
  BarChart3,
  FlaskConical,
  Menu,
  Sun,
  Moon,
} from 'lucide-react'
import { clsx } from 'clsx'

const nav = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/trade', label: 'Nueva operación', icon: PlusCircle },
  { to: '/history', label: 'Histórico', icon: History },
  { to: '/analytics', label: 'Analíticas', icon: BarChart3 },
  { to: '/backtest', label: 'Backtest', icon: FlaskConical },
]

export function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [dark, setDark] = useState(true)

  const toggleTheme = () => {
    setDark((d) => !d)
    document.documentElement.classList.toggle('light', !dark)
  }

  return (
    <div className="min-h-screen bg-[var(--surface)] text-[var(--text)]">
      <aside
        className={clsx(
          'fixed left-0 top-0 z-40 h-screen w-56 border-r border-white/10 bg-[var(--surface-muted)] transition-transform',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="flex h-14 items-center justify-between border-b border-white/10 px-4">
          <span className="font-semibold text-[var(--accent)]">Crypto Sim</span>
          <button
            type="button"
            onClick={() => setSidebarOpen(false)}
            className="rounded p-1 hover:bg-white/10 lg:hidden"
          >
            <Menu className="h-5 w-5" />
          </button>
        </div>
        <nav className="space-y-0.5 p-3">
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-[var(--accent)]/20 text-[var(--accent)]'
                    : 'text-[var(--text-muted)] hover:bg-white/5 hover:text-[var(--text)]'
                )
              }
            >
              <Icon className="h-5 w-5 shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>
      {!sidebarOpen && (
        <button
          type="button"
          onClick={() => setSidebarOpen(true)}
          className="fixed left-2 top-16 z-30 rounded bg-[var(--surface-muted)] p-2 shadow lg:hidden"
        >
          <Menu className="h-5 w-5" />
        </button>
      )}
      <main className={clsx('min-h-screen transition-[margin]', sidebarOpen ? 'lg:ml-56' : 'ml-0')}>
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-white/10 bg-[var(--surface)]/95 px-4 backdrop-blur">
          <h1 className="text-lg font-semibold">Paper Trading · BTCUSDT</h1>
          <button
            type="button"
            onClick={toggleTheme}
            className="rounded-lg p-2 hover:bg-white/10"
            aria-label="Toggle theme"
          >
            {dark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </button>
        </header>
        <div className="p-4 md:p-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
