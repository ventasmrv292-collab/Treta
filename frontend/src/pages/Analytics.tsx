import { useState, useEffect } from 'react'
import { fetchAnalytics } from '../api/endpoints'
import { USE_SUPABASE } from '../config'
import { BarChart3, TrendingUp, PieChart } from 'lucide-react'

interface StrategyComparison {
  strategy_name: string
  strategy_family: string
  total_trades: number
  net_pnl: string
  gross_pnl: string
  total_fees: string
  win_rate: number
  profit_factor: number
  avg_win: string
  avg_loss: string
  expectancy: string
}

interface LeverageComparison {
  leverage: number
  total_trades: number
  net_pnl: string
  win_rate: number
  total_fees: string
}

const PADDING = { top: 12, right: 12, bottom: 24, left: 48 }

function EquityCurveChart({ points }: { points: { time: string; equity: number }[] }) {
  if (points.length === 0) return null
  const w = 600
  const h = 240
  const innerW = w - PADDING.left - PADDING.right
  const innerH = h - PADDING.top - PADDING.bottom
  const values = points.map((p) => p.equity)
  const min = Math.min(...values, 0)
  const max = Math.max(...values, 1)
  const range = max - min || 1
  const scaleY = (v: number) => PADDING.top + innerH - ((v - min) / range) * innerH
  const scaleX = (i: number) => PADDING.left + (i / Math.max(points.length - 1, 1)) * innerW
  const pathD = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${scaleX(i)} ${scaleY(p.equity)}`)
    .join(' ')
  const lineFillD = `${pathD} L ${scaleX(points.length - 1)} ${h - PADDING.bottom} L ${scaleX(0)} ${h - PADDING.bottom} Z`
  return (
    <svg width="100%" height="100%" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="xMidYMid meet" className="overflow-visible">
      <defs>
        <linearGradient id="equityCurveGradient" x1="0" y1="1" x2="0" y2="0">
          <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.25" />
          <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={lineFillD} fill="url(#equityCurveGradient)" />
      <path
        d={pathD}
        fill="none"
        stroke="var(--accent)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <line
        x1={PADDING.left}
        y1={scaleY(0)}
        x2={w - PADDING.right}
        y2={scaleY(0)}
        stroke="var(--text-muted)"
        strokeOpacity="0.4"
        strokeDasharray="4 2"
      />
    </svg>
  )
}

export function Analytics() {
  const [byStrategy, setByStrategy] = useState<StrategyComparison[]>([])
  const [byLeverage, setByLeverage] = useState<LeverageComparison[]>([])
  const [equityCurve, setEquityCurve] = useState<{ time: string; equity: number }[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = () => {
    setError(null)
    setLoading(true)
    fetchAnalytics()
      .then(({ byStrategy: strat, byLeverage: lev, equityCurve: curve }) => {
        setByStrategy(strat ?? [])
        setByLeverage(lev ?? [])
        setEquityCurve(curve?.points ?? [])
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : 'No se pudieron cargar las analíticas')
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center text-[var(--text-muted)]">
        Cargando analíticas...
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-8">
        <h2 className="text-xl font-semibold">Analíticas y comparativas</h2>
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-6 text-sm text-red-200">
          <p className="font-medium">Error al cargar</p>
          <p className="mt-1 text-[var(--text-muted)]">{error}</p>
          <button
            type="button"
            onClick={load}
            className="mt-4 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:opacity-90"
          >
            Reintentar
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-xl font-semibold">Analíticas y comparativas</h2>
        <span
          className="rounded-full px-2.5 py-0.5 text-xs font-medium"
          title={USE_SUPABASE ? 'Datos desde Supabase (Edge Function get-analytics)' : 'Datos desde el backend API (Railway)'}
          style={{
            backgroundColor: USE_SUPABASE ? 'var(--accent)' : 'var(--text-muted)',
            color: 'white',
            opacity: 0.9,
          }}
        >
          {USE_SUPABASE ? 'Supabase' : 'API'}
        </span>
      </div>

      <section className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-6">
        <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-[var(--text-muted)]">
          <BarChart3 className="h-4 w-4" />
          PnL por estrategia
        </h3>
        {byStrategy.length === 0 ? (
          <p className="text-sm text-[var(--text-muted)]">Sin datos de operaciones cerradas. Cierra algunas operaciones para ver PnL por estrategia.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[var(--text-muted)]">
                  <th className="pb-2 font-medium">Estrategia</th>
                  <th className="pb-2 font-medium">Familia</th>
                  <th className="pb-2 font-medium">Trades</th>
                  <th className="pb-2 font-medium">Net PnL</th>
                  <th className="pb-2 font-medium">Fees</th>
                  <th className="pb-2 font-medium">Win rate %</th>
                  <th className="pb-2 font-medium">Profit factor</th>
                </tr>
              </thead>
              <tbody>
                {byStrategy.map((s) => (
                  <tr key={`${s.strategy_family}|${s.strategy_name}`} className="border-t border-white/5">
                    <td className="py-2">{s.strategy_name}</td>
                    <td className="py-2">{s.strategy_family}</td>
                    <td className="py-2">{s.total_trades}</td>
                    <td className={`py-2 font-medium ${parseFloat(s.net_pnl) >= 0 ? 'text-[var(--positive)]' : 'text-[var(--negative)]'}`}>
                      ${parseFloat(s.net_pnl).toFixed(2)}
                    </td>
                    <td className="py-2">${parseFloat(s.total_fees).toFixed(2)}</td>
                    <td className="py-2">{s.win_rate.toFixed(1)}%</td>
                    <td className="py-2">{s.profit_factor.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-6">
        <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-[var(--text-muted)]">
          <PieChart className="h-4 w-4" />
          Comparativa x10 vs x20
        </h3>
        {byLeverage.length === 0 ? (
          <p className="text-sm text-[var(--text-muted)]">Sin datos por apalancamiento. Cierra operaciones con x10/x20 para ver la comparativa.</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {byLeverage.map((l) => (
              <div key={l.leverage} className="rounded-lg border border-white/10 bg-[var(--surface)] p-4">
                <p className="text-lg font-semibold">x{l.leverage}</p>
                <p className="mt-1 text-2xl font-bold text-[var(--accent)]">${parseFloat(l.net_pnl).toFixed(2)}</p>
                <p className="text-sm text-[var(--text-muted)]">Trades: {l.total_trades} · Win rate: {l.win_rate.toFixed(1)}% · Fees: ${parseFloat(l.total_fees).toFixed(2)}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-6">
        <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-[var(--text-muted)]">
          <TrendingUp className="h-4 w-4" />
          Curva de equity (PnL acumulado)
        </h3>
        {equityCurve.length === 0 ? (
          <p className="text-sm text-[var(--text-muted)]">Sin datos de cierres. La curva se construye con el PnL acumulado de cada operación cerrada.</p>
        ) : (
          <div className="h-64 w-full min-h-[200px] flex items-center justify-center bg-[var(--surface)]/50 rounded-lg">
            <EquityCurveChart points={equityCurve} />
          </div>
        )}
      </section>
    </div>
  )
}
