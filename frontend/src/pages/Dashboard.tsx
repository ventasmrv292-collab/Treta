import { useEffect, useState } from 'react'
import { CandlestickChart } from '../components/CandlestickChart'
import { fetchKlines, fetchPrice, fetchDashboard } from '../api/endpoints'
import type { CandleData } from '../types'
import { TrendingUp, TrendingDown, Activity, DollarSign, Percent } from 'lucide-react'

const TIMEFRAMES = ['1m', '5m', '15m', '1h'] as const

/** Intervalo de refresco del precio (ms). 60s para no superar rate limit. */
const PRICE_REFRESH_MS = 60_000
/** Tras error 502/503, esperar más antes del siguiente intento. */
const PRICE_BACKOFF_MS = 90_000
/** Intervalo de refresco del dashboard / métricas (ms). */
const DASHBOARD_REFRESH_MS = 120_000
/** Intervalo de refresco del gráfico de velas (ms). */
const CHART_REFRESH_MS = 30_000

export function Dashboard() {
  const [interval, setInterval] = useState<string>('15m')
  const [candles, setCandles] = useState<CandleData[]>([])
  const [price, setPrice] = useState<string | null>(null)
  const [crosshairPrice, setCrosshairPrice] = useState<number | null>(null)
  const [metrics, setMetrics] = useState<{
    total_trades: number
    win_rate: number
    net_pnl: string
    total_fees: string
    profit_factor: number
    pnl_by_strategy: { strategy_name: string; strategy_family: string; net_pnl: number }[]
    pnl_by_leverage: { leverage: number; net_pnl: number }[]
  } | null>(null)
  const [loading, setLoading] = useState(true)
  const [streamStatus, setStreamStatus] = useState<'idle' | 'loading' | 'ok'>('idle')

  // Carga inicial y al cambiar timeframe: klines + precio + dashboard (una sola rafaga)
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    Promise.all([
      fetchKlines('BTCUSDT', interval, 300),
      fetchPrice('BTCUSDT'),
      fetchDashboard(),
    ])
      .then(([klinesRes, priceRes, dash]) => {
        if (cancelled) return
        setCandles(klinesRes.candles)
        setPrice(priceRes.price)
        setMetrics(dash)
        setStreamStatus('ok')
      })
      .catch(() => {
        if (!cancelled) setStreamStatus('idle')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [interval])

  // Precio: cada 60s; si falla (502/503), siguiente intento en 90s para no saturar
  useEffect(() => {
    let timeoutId: ReturnType<typeof setTimeout>
    const schedule = (delayMs: number) => {
      timeoutId = setTimeout(() => {
        fetchPrice('BTCUSDT')
          .then((r) => {
            setPrice(r.price)
            schedule(PRICE_REFRESH_MS)
          })
          .catch(() => schedule(PRICE_BACKOFF_MS))
      }, delayMs)
    }
    schedule(PRICE_REFRESH_MS)
    return () => clearTimeout(timeoutId)
  }, [])

  // Gráfico de velas: se actualiza solo cada 30 s
  useEffect(() => {
    const t = setInterval(() => {
      fetchKlines('BTCUSDT', interval, 300)
        .then((res) => setCandles(res.candles))
        .catch(() => {})
    }, CHART_REFRESH_MS)
    return () => clearInterval(t)
  }, [interval])

  // Métricas del dashboard: cada 2 min (no en cada cambio de timeframe)
  useEffect(() => {
    const t = setInterval(() => {
      fetchDashboard()
        .then((dash) => setMetrics(dash))
        .catch(() => {})
    }, DASHBOARD_REFRESH_MS)
    return () => clearInterval(t)
  }, [])

  const displayPrice = crosshairPrice ?? (price ? parseFloat(price) : null)

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h2 className="text-xl font-semibold">Dashboard</h2>
        <div className="flex items-center gap-2">
          <span className="text-sm text-[var(--text-muted)]">Timeframe:</span>
          <div className="flex rounded-lg border border-white/10 bg-[var(--surface-muted)] p-0.5">
            {TIMEFRAMES.map((tf) => (
              <button
                key={tf}
                type="button"
                onClick={() => setInterval(tf)}
                className={`rounded px-3 py-1.5 text-sm font-medium transition-colors ${
                  interval === tf ? 'bg-[var(--accent)] text-white' : 'text-[var(--text-muted)] hover:text-[var(--text)]'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>
          <span
            className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-xs ${
              streamStatus === 'ok' ? 'bg-green-500/20 text-green-400' : 'bg-amber-500/20 text-amber-400'
            }`}
          >
            <Activity className="h-3 w-3" />
            {streamStatus === 'ok' ? 'Datos en vivo' : 'Cargando...'}
          </span>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-4">
        <div className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-4">
          <div className="flex items-center gap-2 text-[var(--text-muted)]">
            <DollarSign className="h-4 w-4" />
            <span className="text-sm">Precio BTC</span>
          </div>
          <p className="mt-1 text-2xl font-bold">
            {displayPrice != null ? `$${displayPrice.toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—'}
          </p>
        </div>
        <div className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-4">
          <div className="flex items-center gap-2 text-[var(--text-muted)]">
            <Activity className="h-4 w-4" />
            <span className="text-sm">Total trades</span>
          </div>
          <p className="mt-1 text-2xl font-bold">{metrics?.total_trades ?? '—'}</p>
        </div>
        <div className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-4">
          <div className="flex items-center gap-2 text-[var(--text-muted)]">
            <Percent className="h-4 w-4" />
            <span className="text-sm">Win rate</span>
          </div>
          <p className="mt-1 text-2xl font-bold">{metrics != null ? `${metrics.win_rate}%` : '—'}</p>
        </div>
        <div className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-4">
          <div className="flex items-center gap-2 text-[var(--text-muted)]">
            <TrendingUp className="h-4 w-4" />
            <span className="text-sm">Net PnL</span>
          </div>
          <p
            className={`mt-1 text-2xl font-bold ${
              metrics?.net_pnl && parseFloat(metrics.net_pnl) >= 0 ? 'text-[var(--positive)]' : 'text-[var(--negative)]'
            }`}
          >
            {metrics?.net_pnl != null ? `$${parseFloat(metrics.net_pnl).toFixed(2)}` : '—'}
          </p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-xl border border-white/10 bg-[var(--surface-muted)] p-4">
          <h3 className="mb-4 text-sm font-semibold text-[var(--text-muted)]">BTCUSDT · Velas</h3>
          {loading ? (
            <div className="flex h-[400px] items-center justify-center text-[var(--text-muted)]">Cargando gráfico...</div>
          ) : (
            <CandlestickChart
              data={candles}
              interval={interval}
              onCrosshairMove={setCrosshairPrice}
            />
          )}
        </div>
        <div className="space-y-4">
          <div className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-4">
            <h3 className="mb-3 text-sm font-semibold text-[var(--text-muted)]">Fees pagadas</h3>
            <p className="text-xl font-bold">${metrics?.total_fees != null ? parseFloat(metrics.total_fees).toFixed(2) : '0.00'}</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-4">
            <h3 className="mb-3 text-sm font-semibold text-[var(--text-muted)]">Profit factor</h3>
            <p className="text-xl font-bold">{metrics?.profit_factor != null ? metrics.profit_factor.toFixed(2) : '—'}</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-4">
            <h3 className="mb-3 text-sm font-semibold text-[var(--text-muted)]">PnL por estrategia</h3>
            <ul className="space-y-2">
              {(metrics?.pnl_by_strategy ?? []).map((s) => (
                <li key={s.strategy_name} className="flex justify-between text-sm">
                  <span className="text-[var(--text-muted)]">{s.strategy_name}</span>
                  <span className={s.net_pnl >= 0 ? 'text-[var(--positive)]' : 'text-[var(--negative)]'}>
                    ${s.net_pnl.toFixed(2)}
                  </span>
                </li>
              ))}
              {(!metrics?.pnl_by_strategy?.length) && <li className="text-sm text-[var(--text-muted)]">Sin datos</li>}
            </ul>
          </div>
          <div className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-4">
            <h3 className="mb-3 text-sm font-semibold text-[var(--text-muted)]">PnL por leverage</h3>
            <ul className="space-y-2">
              {(metrics?.pnl_by_leverage ?? []).map((l) => (
                <li key={l.leverage} className="flex justify-between text-sm">
                  <span className="text-[var(--text-muted)]">x{l.leverage}</span>
                  <span className={l.net_pnl >= 0 ? 'text-[var(--positive)]' : 'text-[var(--negative)]'}>
                    ${l.net_pnl.toFixed(2)}
                  </span>
                </li>
              ))}
              {(!metrics?.pnl_by_leverage?.length) && <li className="text-sm text-[var(--text-muted)]">Sin datos</li>}
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
