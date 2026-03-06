import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { CandlestickChart } from '../components/CandlestickChart'
import { fetchKlines, fetchPrice, fetchDashboard, fetchPaperAccounts, fetchDashboardSummary, fetchTrades } from '../api/endpoints'
import { WS_BASE } from '../config'
import type { CandleData, PaperAccount, Trade } from '../types'
import { format } from 'date-fns'
import { TrendingUp, Activity, DollarSign, Percent, Wallet, History, ArrowRight } from 'lucide-react'

const TIMEFRAMES = ['1m', '5m', '15m', '1h'] as const

/** Intervalo de refresco del precio (ms). */
const PRICE_REFRESH_MS = 10_000
/** Tras error 502/503, esperar más antes del siguiente intento. */
const PRICE_BACKOFF_MS = 30_000
/** Intervalo de refresco del dashboard / métricas (ms). */
const DASHBOARD_REFRESH_MS = 120_000
/** Intervalo de refresco del gráfico de velas (ms). */
const CHART_REFRESH_MS = 10_000

export function Dashboard() {
  const [interval, setInterval] = useState<string>('15m')
  const [candles, setCandles] = useState<CandleData[]>([])
  const [price, setPrice] = useState<string | null>(null)
  const [livePrice, setLivePrice] = useState<number | null>(null)
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
  const [paperAccounts, setPaperAccounts] = useState<PaperAccount[]>([])
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null)
  const [accountSummary, setAccountSummary] = useState<{
    initial_balance_usdt: string
    current_balance_usdt: string
    available_balance_usdt: string
    used_margin_usdt: string
    total_fees_usdt: string
    equity_usdt: string | null
  } | null>(null)
  const [recentTrades, setRecentTrades] = useState<Trade[]>([])

  // Carga inicial: klines, precio, cuentas paper y dashboard (o summary con cuenta)
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    Promise.all([
      fetchKlines('BTCUSDT', interval, 300),
      fetchPrice('BTCUSDT'),
      fetchPaperAccounts(),
    ])
      .then(([klinesRes, priceRes, accounts]) => {
        if (cancelled) return
        setCandles(klinesRes.candles)
        setPrice(priceRes.price)
        setPaperAccounts(accounts)
        const accountId = accounts.length > 0 ? accounts[0].id : null
        setSelectedAccountId(accountId)
        if (accountId != null) {
          return fetchDashboardSummary(accountId).then((summary) => {
            if (cancelled) return
            setMetrics({
              total_trades: summary.total_trades,
              win_rate: summary.win_rate,
              net_pnl: summary.net_pnl,
              total_fees: summary.total_fees,
              profit_factor: summary.profit_factor,
              pnl_by_strategy: summary.pnl_by_strategy,
              pnl_by_leverage: summary.pnl_by_leverage,
            })
            if (summary.account) {
              setAccountSummary({
                initial_balance_usdt: summary.account.initial_balance_usdt,
                current_balance_usdt: summary.account.current_balance_usdt,
                available_balance_usdt: summary.account.available_balance_usdt,
                used_margin_usdt: summary.account.used_margin_usdt,
                total_fees_usdt: summary.account.total_fees_usdt,
                equity_usdt: summary.equity_usdt ?? null,
              })
            }
            setStreamStatus('ok')
          })
        }
        return fetchDashboard().then((dash) => {
          if (cancelled) return
          setMetrics(dash)
          setStreamStatus('ok')
        })
      })
      .catch(() => {
        if (!cancelled) setStreamStatus('idle')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [interval])

  // WebSocket: precio en tiempo real (reconexión automática)
  useEffect(() => {
    const wsUrl = `${WS_BASE}/api/v1/ws/price`
    let ws: WebSocket | null = null
    let reconnectTimer: ReturnType<typeof setTimeout>

    const connect = () => {
      ws = new WebSocket(wsUrl)
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as { price?: string }
          if (data.price != null) setLivePrice(parseFloat(data.price))
        } catch {
          // ignore
        }
      }
      ws.onclose = () => {
        ws = null
        reconnectTimer = setTimeout(connect, 3000)
      }
      ws.onerror = () => {
        ws?.close()
      }
    }
    connect()
    return () => {
      clearTimeout(reconnectTimer)
      ws?.close()
    }
  }, [])

  // Precio por polling (fallback cuando WS no está disponible)
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

  // Historial reciente (parte inferior del dashboard)
  useEffect(() => {
    fetchTrades({ page: 1, size: 10 })
      .then((r) => setRecentTrades(r.items))
      .catch(() => setRecentTrades([]))
  }, [])
  useEffect(() => {
    const t = setInterval(() => {
      fetchTrades({ page: 1, size: 10 })
        .then((r) => setRecentTrades(r.items))
        .catch(() => {})
    }, DASHBOARD_REFRESH_MS)
    return () => clearInterval(t)
  }, [])

  // Refresco métricas: si hay cuenta seleccionada, dashboard-summary; si no, dashboard
  useEffect(() => {
    const t = setInterval(() => {
      if (selectedAccountId != null) {
        fetchDashboardSummary(selectedAccountId)
          .then((summary) => {
            setMetrics({
              total_trades: summary.total_trades,
              win_rate: summary.win_rate,
              net_pnl: summary.net_pnl,
              total_fees: summary.total_fees,
              profit_factor: summary.profit_factor,
              pnl_by_strategy: summary.pnl_by_strategy,
              pnl_by_leverage: summary.pnl_by_leverage,
            })
            if (summary.account)
              setAccountSummary({
                initial_balance_usdt: summary.account.initial_balance_usdt,
                current_balance_usdt: summary.account.current_balance_usdt,
                available_balance_usdt: summary.account.available_balance_usdt,
                used_margin_usdt: summary.account.used_margin_usdt,
                total_fees_usdt: summary.account.total_fees_usdt,
                equity_usdt: summary.equity_usdt ?? null,
              })
          })
          .catch(() => {})
      } else {
        fetchDashboard().then((dash) => setMetrics(dash)).catch(() => {})
      }
    }, DASHBOARD_REFRESH_MS)
    return () => clearInterval(t)
  }, [selectedAccountId])

  // Precio mostrado: ratón en gráfico > WebSocket en vivo > cierre última vela > polling
  const lastCandleClose = candles.length > 0 ? candles[candles.length - 1].close : null
  const displayPrice = crosshairPrice ?? livePrice ?? lastCandleClose ?? (price ? parseFloat(price) : null)

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

      {/* Capital / Cuenta Paper: siempre visible en el dashboard principal */}
      <div className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-4">
        <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-[var(--text-muted)]">
          <Wallet className="h-4 w-4" />
          Capital · Cuenta Paper
          {paperAccounts.length > 1 && accountSummary && (
              <select
                className="ml-2 rounded border border-white/10 bg-[var(--bg)] px-2 py-1 text-sm text-[var(--text)]"
                value={selectedAccountId ?? ''}
                onChange={(e) => {
                  const id = Number(e.target.value)
                  if (!Number.isNaN(id)) {
                    setSelectedAccountId(id)
                    fetchDashboardSummary(id).then((s) => {
                      if (s.account)
                        setAccountSummary({
                          initial_balance_usdt: s.account.initial_balance_usdt,
                          current_balance_usdt: s.account.current_balance_usdt,
                          available_balance_usdt: s.account.available_balance_usdt,
                          used_margin_usdt: s.account.used_margin_usdt,
                          total_fees_usdt: s.account.total_fees_usdt,
                          equity_usdt: s.equity_usdt ?? null,
                        })
                    })
                  }
                }}
              >
                {paperAccounts.map((a) => (
                  <option key={a.id} value={a.id}>{a.name}</option>
                ))}
              </select>
            )}
          </h3>
          {accountSummary ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
              <div className="rounded-lg border border-white/5 bg-black/20 p-3">
                <p className="text-xs text-[var(--text-muted)]">Capital inicial</p>
                <p className="text-lg font-semibold">${parseFloat(accountSummary.initial_balance_usdt).toFixed(2)}</p>
              </div>
              <div className="rounded-lg border border-white/5 bg-black/20 p-3">
                <p className="text-xs text-[var(--text-muted)]">Balance actual</p>
                <p className="text-lg font-semibold">${parseFloat(accountSummary.current_balance_usdt).toFixed(2)}</p>
              </div>
              <div className="rounded-lg border border-white/5 bg-black/20 p-3">
                <p className="text-xs text-[var(--text-muted)]">Equity</p>
                <p className="text-lg font-semibold">
                  ${accountSummary.equity_usdt != null ? parseFloat(accountSummary.equity_usdt).toFixed(2) : parseFloat(accountSummary.current_balance_usdt).toFixed(2)}
                </p>
              </div>
              <div className="rounded-lg border border-white/5 bg-black/20 p-3">
                <p className="text-xs text-[var(--text-muted)]">Capital disponible</p>
                <p className="text-lg font-semibold">${parseFloat(accountSummary.available_balance_usdt).toFixed(2)}</p>
              </div>
              <div className="rounded-lg border border-white/5 bg-black/20 p-3">
                <p className="text-xs text-[var(--text-muted)]">Margen usado</p>
                <p className="text-lg font-semibold">${parseFloat(accountSummary.used_margin_usdt).toFixed(2)}</p>
              </div>
              <div className="rounded-lg border border-white/5 bg-black/20 p-3">
                <p className="text-xs text-[var(--text-muted)]">Fees acumuladas</p>
                <p className="text-lg font-semibold">${parseFloat(accountSummary.total_fees_usdt).toFixed(2)}</p>
              </div>
            </div>
          ) : (
            <p className="text-sm text-[var(--text-muted)]">
              {loading ? 'Cargando cuenta...' : 'No hay cuenta paper. Ejecuta en Supabase el seed docs/seeds/001_initial_seed.sql (después de las migraciones) para crear la cuenta por defecto.'}
            </p>
          )}
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
              livePrice={livePrice}
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

      {/* Historial reciente en la parte inferior */}
      <div className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-4">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-[var(--text-muted)]">
            <History className="h-4 w-4" />
            Historial reciente
          </h3>
          <Link
            to="/history"
            className="flex items-center gap-1 rounded-lg border border-white/10 px-3 py-1.5 text-sm font-medium hover:bg-white/5"
          >
            Ver todo
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[500px] text-sm">
            <thead>
              <tr className="border-b border-white/10 text-left text-[var(--text-muted)]">
                <th className="p-2 font-medium">Fecha</th>
                <th className="p-2 font-medium">Símbolo</th>
                <th className="p-2 font-medium">L/S</th>
                <th className="p-2 font-medium">Entrada</th>
                <th className="p-2 font-medium">Salida</th>
                <th className="p-2 font-medium">PnL neto</th>
                <th className="p-2 font-medium">Estado</th>
              </tr>
            </thead>
            <tbody>
              {recentTrades.length === 0 && (
                <tr>
                  <td colSpan={7} className="p-6 text-center text-[var(--text-muted)]">
                    No hay operaciones. <Link to="/trade" className="text-[var(--accent)] hover:underline">Nueva operación</Link>
                  </td>
                </tr>
              )}
              {recentTrades.map((t) => (
                <tr key={t.id} className="border-b border-white/5 hover:bg-white/5">
                  <td className="p-2">{format(new Date(t.created_at), 'dd/MM/yy HH:mm')}</td>
                  <td className="p-2">{t.symbol}</td>
                  <td className="p-2">{t.position_side}</td>
                  <td className="p-2">{t.entry_price}</td>
                  <td className="p-2">{t.exit_price ?? '—'}</td>
                  <td className={`p-2 font-medium ${t.net_pnl_usdt != null && parseFloat(t.net_pnl_usdt) >= 0 ? 'text-[var(--positive)]' : 'text-[var(--negative)]'}`}>
                    {t.net_pnl_usdt != null ? `$${parseFloat(t.net_pnl_usdt).toFixed(2)}` : '—'}
                  </td>
                  <td className="p-2">{t.status ?? (t.closed_at ? 'CLOSED' : 'OPEN')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
