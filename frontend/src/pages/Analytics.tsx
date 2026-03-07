import { useState, useEffect } from 'react'
import { fetchAnalytics } from '../api/endpoints'
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

export function Analytics() {
  const [byStrategy, setByStrategy] = useState<StrategyComparison[]>([])
  const [byLeverage, setByLeverage] = useState<LeverageComparison[]>([])
  const [equityCurve, setEquityCurve] = useState<{ time: string; equity: number }[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchAnalytics()
      .then(({ byStrategy: strat, byLeverage: lev, equityCurve: curve }) => {
        setByStrategy(strat)
        setByLeverage(lev)
        setEquityCurve(curve.points || [])
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center text-[var(--text-muted)]">
        Cargando analíticas...
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <h2 className="text-xl font-semibold">Analíticas y comparativas</h2>

      <section className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-6">
        <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-[var(--text-muted)]">
          <BarChart3 className="h-4 w-4" />
          PnL por estrategia
        </h3>
        {byStrategy.length === 0 ? (
          <p className="text-sm text-[var(--text-muted)]">Sin datos de operaciones cerradas.</p>
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
                  <tr key={s.strategy_name} className="border-t border-white/5">
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
          <p className="text-sm text-[var(--text-muted)]">Sin datos.</p>
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
          <p className="text-sm text-[var(--text-muted)]">Sin datos de cierres.</p>
        ) : (
          <div className="h-64 overflow-x-auto">
            <div className="flex h-full min-w-[400px] items-end gap-0.5">
              {equityCurve.map((p, i) => {
                const max = Math.max(...equityCurve.map((x) => x.equity), 1)
                const min = Math.min(...equityCurve.map((x) => x.equity), 0)
                const range = max - min || 1
                const h = ((p.equity - min) / range) * 100
                return (
                  <div
                    key={i}
                    title={`${p.time} → $${p.equity.toFixed(2)}`}
                    className="flex-1 rounded-t bg-[var(--accent)]/60 transition hover:bg-[var(--accent)]"
                    style={{ height: `${Math.max(2, h)}%` }}
                  />
                )
              })}
            </div>
          </div>
        )}
      </section>
    </div>
  )
}
