import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import {
  LayoutDashboard,
  PlusCircle,
  History,
  BarChart3,
  FlaskConical,
  PanelLeftClose,
  PanelLeft,
  Sun,
  Moon,
  HelpCircle,
  Languages,
} from 'lucide-react'
import { clsx } from 'clsx'
import { useI18n } from '../contexts/I18nContext'

const navKeys = [
  { to: '/dashboard', key: 'nav.dashboard', icon: LayoutDashboard },
  { to: '/trade', key: 'nav.newTrade', icon: PlusCircle },
  { to: '/history', key: 'nav.history', icon: History },
  { to: '/analytics', key: 'nav.analytics', icon: BarChart3 },
  { to: '/backtest', key: 'nav.backtest', icon: FlaskConical },
  { to: '/ayuda', key: 'nav.howItWorks', icon: HelpCircle },
] as const

export function Layout() {
  const { t, locale, setLocale } = useI18n()
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [dark, setDark] = useState(true)

  const toggleTheme = () => {
    setDark((d) => !d)
    document.documentElement.classList.toggle('light', !dark)
  }

  const toggleLocale = () => {
    setLocale(locale === 'es' ? 'pt-PT' : 'es')
  }

  return (
    <div className="min-h-screen bg-[var(--surface)] text-[var(--text)]">
      <aside
        className={clsx(
          'fixed left-0 top-0 z-40 h-screen w-56 border-r border-white/10 bg-[var(--surface-muted)] transition-[transform] duration-500 ease-in-out',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="flex h-14 items-center justify-between border-b border-white/10 px-4">
          <span className="font-semibold text-[var(--accent)]">TRETA</span>
          <button
            type="button"
            onClick={() => setSidebarOpen(false)}
            className="rounded p-1.5 hover:bg-white/10 transition-colors"
            aria-label="Ocultar menú"
          >
            <PanelLeftClose className="h-5 w-5" />
          </button>
        </div>
        <nav className="space-y-0.5 p-3">
          {navKeys.map(({ to, key, icon: Icon }) => (
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
              {t(key)}
            </NavLink>
          ))}
        </nav>
      </aside>
      <button
        type="button"
        onClick={() => setSidebarOpen(true)}
        className={clsx(
          'fixed left-0 top-20 z-30 flex h-10 w-6 items-center justify-center rounded-r-md border border-l-0 border-white/10 bg-[var(--surface-muted)] shadow-sm transition-all duration-500 ease-in-out hover:bg-white/10 hover:scale-105',
          sidebarOpen ? '-translate-x-full opacity-0 pointer-events-none' : 'translate-x-0 opacity-100'
        )}
        aria-label="Mostrar menú"
      >
        <PanelLeft className="h-4 w-4 text-[var(--text-muted)]" />
      </button>
      <main
        className={clsx(
          'min-h-screen transition-[margin-left] duration-500 ease-in-out',
          sidebarOpen ? 'ml-0 lg:ml-56' : 'ml-0'
        )}
      >
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-2 border-b border-white/10 bg-[var(--surface)]/95 px-4 backdrop-blur">
          <button
            type="button"
            onClick={() => setSidebarOpen((v) => !v)}
            className="rounded-lg p-2 hover:bg-white/10 transition-colors shrink-0"
            aria-label={sidebarOpen ? 'Ocultar menú' : 'Mostrar menú'}
          >
            {sidebarOpen ? <PanelLeftClose className="h-5 w-5" /> : <PanelLeft className="h-5 w-5" />}
          </button>
          <h1 className="text-lg font-semibold truncate min-w-0">{t('common.paperTrading')}</h1>
          <div className="flex items-center gap-1 shrink-0">
            <button
              type="button"
              onClick={toggleLocale}
              className="flex items-center gap-1.5 rounded-lg px-2.5 py-2 hover:bg-white/10 transition-colors text-sm font-medium"
              title={locale === 'es' ? 'Mudar para Português' : 'Cambiar a Español'}
              aria-label={locale === 'es' ? 'Traducir a portugués' : 'Translate to Portuguese'}
            >
              <Languages className="h-5 w-5 text-[var(--accent)]" />
              <span className="hidden sm:inline">{t('common.localeName')}</span>
            </button>
            <button
              type="button"
              onClick={toggleTheme}
              className="rounded-lg p-2 hover:bg-white/10 transition-colors"
              aria-label="Toggle theme"
            >
              {dark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </button>
          </div>
        </header>
        <div className="p-4 md:p-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
