import { Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { NewTrade } from './pages/NewTrade'
import { History } from './pages/History'
import { Analytics } from './pages/Analytics'
import { Backtest } from './pages/Backtest'
import { Toaster } from './components/Toaster'

function NotFound() {
  const navigate = useNavigate()
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-[var(--text)]">
      <p className="text-2xl font-semibold">404</p>
      <p className="text-[var(--text-muted)]">Página no encontrada</p>
      <button
        type="button"
        onClick={() => navigate('/dashboard')}
        className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:opacity-90"
      >
        Ir al Dashboard
      </button>
    </div>
  )
}

function App() {
  return (
    <Toaster>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/" element={<Layout />}>
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="trade" element={<NewTrade />} />
          <Route path="history" element={<History />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="backtest" element={<Backtest />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Toaster>
  )
}

export default App
