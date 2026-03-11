import { useState, useEffect } from 'react'
import { fetchAnalytics, fetchRuntimeRecommendations, fetchByStrategyVersion, type RuntimeRecommendations, type StrategyVersionRow } from '../api/endpoints'
import { USE_SUPABASE } from '../config'
import { useI18n } from '../contexts/I18nContext'
import { BarChart3, TrendingUp, PieChart, GitCompare } from 'lucide-react'

interface StrategyComparison {
  strategy_name: string
  strategy_family: string
  strategy_version?: string
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
  const { t } = useI18n()
  const [byStrategy, setByStrategy] = useState<StrategyComparison[]>([])
  const [byLeverage, setByLeverage] = useState<LeverageComparison[]>([])
  const [byStrategyVersion, setByStrategyVersion] = useState<StrategyVersionRow[]>([])
  const [equityCurve, setEquityCurve] = useState<{ time: string; equity: number }[]>([])
  const [runtimeRec, setRuntimeRec] = useState<RuntimeRecommendations | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = () => {
    setError(null)
    setLoading(true)
    const all = USE_SUPABASE
      ? Promise.all([fetchAnalytics(), fetchRuntimeRecommendations(7).catch(() => null)])
      : Promise.all([fetchAnalytics(), fetchRuntimeRecommendations(7).catch(() => null), fetchByStrategyVersion().catch(() => [])])
    all
      .then((results) => {
        const analytics = results[0]
        const rec = results[1] as RuntimeRecommendations | null
        const v2 = results[2] as StrategyVersionRow[] | undefined
        const { byStrategy: strat, byLeverage: lev, equityCurve: curve } = analytics
        setByStrategy(strat ?? [])
        setByLeverage(lev ?? [])
        setEquityCurve(curve?.points ?? [])
        setRuntimeRec(rec ?? null)
        if (Array.isArray(v2)) setByStrategyVersion(v2)
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
        {t('analytics.loading')}
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-8">
        <h2 className="text-xl font-semibold">{t('analytics.title')}</h2>
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-6 text-sm text-red-200">
          <p className="font-medium">{t('analytics.errorTitle')}</p>
          <p className="mt-1 text-[var(--text-muted)]">{error}</p>
          <button
            type="button"
            onClick={load}
            className="mt-4 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:opacity-90"
          >
            {t('analytics.retry')}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-xl font-semibold">{t('analytics.title')}</h2>
        <span
          className="rounded-full px-2.5 py-0.5 text-xs font-medium"
          title={USE_SUPABASE ? 'Datos desde Supabase (Edge Function get-analytics)' : 'Datos desde el backend API (Railway)'}
          style={{
            backgroundColor: USE_SUPABASE ? 'var(--accent)' : 'var(--text-muted)',
            color: 'white',
            opacity: 0.9,
          }}
        >
          {USE_SUPABASE ? t('analytics.supabase') : t('analytics.api')}
        </span>
      </div>

      {runtimeRec && (
        <section className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-6">
          <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-amber-200">
            {t('analytics.recommendationsTitle', { days: runtimeRec.window_days })}
          </h3>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 text-sm">
            {runtimeRec.best_strategy && (
              <div className="rounded-lg border border-white/10 bg-[var(--surface)] p-3">
                <p className="text-[var(--text-muted)]">{t('analytics.bestStrategy')}</p>
                <p className="font-medium text-[var(--positive)]">{runtimeRec.best_strategy.strategy_name}</p>
                <p className="text-xs">PnL: ${runtimeRec.best_strategy.net_pnl.toFixed(2)}</p>
              </div>
            )}
            {runtimeRec.worst_strategy && (
              <div className="rounded-lg border border-white/10 bg-[var(--surface)] p-3">
                <p className="text-[var(--text-muted)]">{t('analytics.worstStrategy')}</p>
                <p className="font-medium text-[var(--negative)]">{runtimeRec.worst_strategy.strategy_name}</p>
                <p className="text-xs">PnL: ${runtimeRec.worst_strategy.net_pnl.toFixed(2)}</p>
              </div>
            )}
            {runtimeRec.best_timeframe && (
              <div className="rounded-lg border border-white/10 bg-[var(--surface)] p-3">
                <p className="text-[var(--text-muted)]">{t('analytics.bestTimeframe')}</p>
                <p className="font-medium text-[var(--positive)]">{runtimeRec.best_timeframe.timeframe}</p>
                <p className="text-xs">PnL: ${runtimeRec.best_timeframe.net_pnl.toFixed(2)}</p>
              </div>
            )}
            {runtimeRec.worst_timeframe && (
              <div className="rounded-lg border border-white/10 bg-[var(--surface)] p-3">
                <p className="text-[var(--text-muted)]">{t('analytics.worstTimeframe')}</p>
                <p className="font-medium text-[var(--negative)]">{runtimeRec.worst_timeframe.timeframe}</p>
                <p className="text-xs">PnL: ${runtimeRec.worst_timeframe.net_pnl.toFixed(2)}</p>
              </div>
            )}
          </div>
          {runtimeRec.recommendations.length > 0 && (
            <ul className="mt-4 list-inside list-disc space-y-1 text-sm text-amber-100/90">
              {runtimeRec.recommendations.map((rec, i) => (
                <li key={i}>{rec}</li>
              ))}
            </ul>
          )}
        </section>
      )}

      <section className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-6">
        <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-[var(--text-muted)]">
          <BarChart3 className="h-4 w-4" />
          {t('analytics.pnlByStrategy')}
        </h3>
        {byStrategy.length === 0 ? (
          <p className="text-sm text-[var(--text-muted)]">{t('analytics.noDataStrategy')}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[var(--text-muted)]">
                  <th className="pb-2 font-medium">{t('analytics.strategy')}</th>
                  <th className="pb-2 font-medium">{t('analytics.family')}</th>
                  <th className="pb-2 font-medium">{t('analytics.version')}</th>
                  <th className="pb-2 font-medium">{t('analytics.trades')}</th>
                  <th className="pb-2 font-medium">{t('analytics.netPnl')}</th>
                  <th className="pb-2 font-medium">{t('analytics.fees')}</th>
                  <th className="pb-2 font-medium">{t('analytics.winRatePct')}</th>
                  <th className="pb-2 font-medium">{t('analytics.profitFactor')}</th>
                </tr>
              </thead>
              <tbody>
                {byStrategy.map((s) => (
                  <tr key={`${s.strategy_family}|${s.strategy_name}|${s.strategy_version ?? ''}`} className="border-t border-white/5">
                    <td className="py-2">{s.strategy_name}</td>
                    <td className="py-2">{s.strategy_family}</td>
                    <td className="py-2">
                      <span className={s.strategy_version?.startsWith('2') ? 'text-[var(--accent)] font-medium' : ''}>
                        {s.strategy_version ?? '—'}
                      </span>
                    </td>
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

      {!USE_SUPABASE && byStrategyVersion.length > 0 && (
        <section className="rounded-xl border border-[var(--accent)]/20 bg-[var(--surface-muted)] p-6">
          <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-[var(--accent)]">
            <GitCompare className="h-4 w-4" />
            {t('analytics.v1vsV2')}
          </h3>
          <p className="mb-4 text-xs text-[var(--text-muted)]">{t('analytics.v1vsV2Desc')}</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[var(--text-muted)]">
                  <th className="pb-2 font-medium">{t('analytics.strategy')}</th>
                  <th className="pb-2 font-medium">{t('analytics.version')}</th>
                  <th className="pb-2 font-medium">{t('analytics.timeframe')}</th>
                  <th className="pb-2 font-medium">{t('analytics.side')}</th>
                  <th className="pb-2 font-medium">{t('analytics.trades')}</th>
                  <th className="pb-2 font-medium">{t('analytics.netPnl')}</th>
                  <th className="pb-2 font-medium">{t('analytics.slippageTotal')}</th>
                  <th className="pb-2 font-medium">{t('analytics.winRatePct')}</th>
                </tr>
              </thead>
              <tbody>
                {byStrategyVersion.map((row, i) => (
                  <tr key={i} className="border-t border-white/5">
                    <td className="py-2">{row.strategy_name}</td>
                    <td className="py-2">
                      <span className={row.strategy_version.startsWith('2') ? 'text-[var(--accent)] font-medium' : ''}>
                        {row.strategy_version}
                      </span>
                    </td>
                    <td className="py-2">{row.timeframe}</td>
                    <td className="py-2">{row.position_side}</td>
                    <td className="py-2">{row.total_trades}</td>
                    <td className={`py-2 font-medium ${parseFloat(row.net_pnl) >= 0 ? 'text-[var(--positive)]' : 'text-[var(--negative)]'}`}>
                      ${parseFloat(row.net_pnl).toFixed(2)}
                    </td>
                    <td className="py-2">${parseFloat(row.total_slippage_usdt).toFixed(2)}</td>
                    <td className="py-2">{row.win_rate.toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-6">
        <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-[var(--text-muted)]">
          <PieChart className="h-4 w-4" />
          {t('analytics.compareX10X20')}
        </h3>
        {byLeverage.length === 0 ? (
          <p className="text-sm text-[var(--text-muted)]">{t('analytics.noDataLeverage')}</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {byLeverage.map((l) => (
              <div key={l.leverage} className="rounded-lg border border-white/10 bg-[var(--surface)] p-4">
                <p className="text-lg font-semibold">x{l.leverage}</p>
                <p className="mt-1 text-2xl font-bold text-[var(--accent)]">${parseFloat(l.net_pnl).toFixed(2)}</p>
                <p className="text-sm text-[var(--text-muted)]">{t('analytics.tradesLabel')}: {l.total_trades} · Win rate: {l.win_rate.toFixed(1)}% · {t('analytics.fees')}: ${parseFloat(l.total_fees).toFixed(2)}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-6">
        <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-[var(--text-muted)]">
          <TrendingUp className="h-4 w-4" />
          {t('analytics.equityCurve')}
        </h3>
        {equityCurve.length === 0 ? (
          <p className="text-sm text-[var(--text-muted)]">{t('analytics.noDataEquityCurve')}</p>
        ) : (
          <div className="h-64 w-full min-h-[200px] flex items-center justify-center bg-[var(--surface)]/50 rounded-lg">
            <EquityCurveChart points={equityCurve} />
          </div>
        )}
      </section>
    </div>
  )
}
