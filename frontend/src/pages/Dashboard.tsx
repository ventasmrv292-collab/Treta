import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { CandlestickChart } from '../components/CandlestickChart'
import { fetchKlines, fetchPrice, fetchDashboard, fetchPaperAccounts, fetchDashboardSummary, fetchTrades, fetchSupervisorStatus, fetchSchedulerStatus, fetchBotLogs } from '../api/endpoints'
import { EventExplanationModal } from '../components/EventExplanationModal'
import { getEventExplanation } from '../constants/eventExplanations'
import { useI18n } from '../contexts/I18nContext'
import { WS_BASE } from '../config'
import type { CandleData, PaperAccount, Trade } from '../types'
import type { StrategyOverlayId } from '../utils/strategyIndicators'
import { format } from 'date-fns'
import { TrendingUp, Activity, DollarSign, Percent, Wallet, History, ArrowRight, Bot, FileText } from 'lucide-react'

const TIMEFRAMES = ['15m', '30m', '1h'] as const

/** Intervalo de refresco del precio (ms). */
const PRICE_REFRESH_MS = 10_000
/** Tras error 502/503, esperar más antes del siguiente intento. */
const PRICE_BACKOFF_MS = 30_000
/** Intervalo de refresco del dashboard / métricas (ms). */
const DASHBOARD_REFRESH_MS = 120_000
/** Intervalo de refresco del gráfico de velas (ms). */
const CHART_REFRESH_MS = 10_000

export function Dashboard() {
  const { t } = useI18n()
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
    realized_pnl_usdt?: string
    unrealized_pnl_usdt?: string
    open_positions_count?: number
  } | null>(null)
  const [recentTrades, setRecentTrades] = useState<Trade[]>([])
  const [supervisorStatus, setSupervisorStatus] = useState<{ running: boolean; last_cycle_at: number | null; check_interval_seconds: number } | null>(null)
  const [schedulerStatus, setSchedulerStatus] = useState<{ running: boolean; started_at: number | null; jobs: Record<string, { last_run_at?: number; last_error?: string }> } | null>(null)
  const [botLogs, setBotLogs] = useState<{ id: number; level: string; event_type: string; message: string; created_at: string }[]>([])
  const [eventTypeForHelp, setEventTypeForHelp] = useState<string | null>(null)
  const [strategyOverlay, setStrategyOverlay] = useState<StrategyOverlayId | null>(null)
  const [candlesError, setCandlesError] = useState<string | null>(null)
  /** Fuente actual de datos de mercado (binance, bybit, coingecko). */
  const [marketDataSource, setMarketDataSource] = useState<string | null>(null)

  // Carga inicial: klines, precio, cuentas paper y dashboard (o summary con cuenta)
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setCandlesError(null)
    Promise.all([
      fetchKlines('BTCUSDT', interval, 300),
      fetchPrice('BTCUSDT'),
      fetchPaperAccounts(),
    ])
      .then(([klinesRes, priceRes, accounts]) => {
        if (cancelled) return
        setCandles(klinesRes.candles)
        setCandlesError(null)
        setPrice(priceRes.price)
        setMarketDataSource(klinesRes.source ?? priceRes.source ?? null)
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
                realized_pnl_usdt: summary.account.realized_pnl_usdt,
                unrealized_pnl_usdt: summary.account.unrealized_pnl_usdt,
                open_positions_count: summary.open_positions_count ?? 0,
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
      .catch((err: Error) => {
        if (!cancelled) {
          setStreamStatus('idle')
          setCandlesError(err?.message ?? 'No se pudieron cargar las velas.')
        }
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
            if (r.source) setMarketDataSource(r.source)
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
        .then((res) => {
          setCandles(res.candles)
          if (res.source) setMarketDataSource(res.source)
        })
        .catch(() => {})
    }, CHART_REFRESH_MS)
    return () => clearInterval(t)
  }, [interval])

  // Supervisor y bot logs
  useEffect(() => {
    fetchSupervisorStatus().then(setSupervisorStatus).catch(() => setSupervisorStatus(null))
    fetchSchedulerStatus().then(setSchedulerStatus).catch(() => setSchedulerStatus(null))
    fetchBotLogs({ limit: 15 }).then((logs) => setBotLogs(logs)).catch(() => setBotLogs([]))
  }, [])
  useEffect(() => {
    const t = setInterval(() => {
      fetchSupervisorStatus().then(setSupervisorStatus).catch(() => {})
      fetchSchedulerStatus().then(setSchedulerStatus).catch(() => {})
      fetchBotLogs({ limit: 15 }).then((logs) => setBotLogs(logs)).catch(() => {})
    }, 30000)
    return () => clearInterval(t)
  }, [])

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
                realized_pnl_usdt: summary.account.realized_pnl_usdt,
                unrealized_pnl_usdt: summary.account.unrealized_pnl_usdt,
                open_positions_count: summary.open_positions_count ?? 0,
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
        <h2 className="text-xl font-semibold">{t('dashboard.title')}</h2>
        <div className="flex items-center gap-2">
          <span className="text-sm text-[var(--text-muted)]">{t('dashboard.timeframe')}:</span>
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
            {streamStatus === 'ok' ? t('dashboard.liveData') : t('common.loading')}
          </span>
          {marketDataSource && (
            <span className="flex items-center gap-1 rounded-full bg-slate-600/40 px-2 py-0.5 text-xs text-[var(--text-muted)]" title={t('dashboard.dataSource')}>
              {t('dashboard.dataSource')}: {marketDataSource === 'binance' ? t('dashboard.dataSourceBinance') : marketDataSource === 'bybit' ? t('dashboard.dataSourceBybit') : t('dashboard.dataSourceCoingecko')}
            </span>
          )}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-4">
        <div className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-4">
          <div className="flex items-center gap-2 text-[var(--text-muted)]">
            <DollarSign className="h-4 w-4" />
            <span className="text-sm">{t('dashboard.btcPrice')}</span>
          </div>
          <p className="mt-1 text-2xl font-bold">
            {displayPrice != null ? `$${displayPrice.toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—'}
          </p>
        </div>
        <div className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-4">
          <div className="flex items-center gap-2 text-[var(--text-muted)]">
            <Activity className="h-4 w-4" />
            <span className="text-sm">{t('dashboard.totalTrades')}</span>
          </div>
          <p className="mt-1 text-2xl font-bold">{metrics?.total_trades ?? '—'}</p>
        </div>
        <div className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-4">
          <div className="flex items-center gap-2 text-[var(--text-muted)]">
            <Percent className="h-4 w-4" />
            <span className="text-sm">{t('dashboard.winRate')}</span>
          </div>
          <p className="mt-1 text-2xl font-bold">{metrics != null ? `${metrics.win_rate}%` : '—'}</p>
        </div>
        <div className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-4">
          <div className="flex items-center gap-2 text-[var(--text-muted)]">
            <TrendingUp className="h-4 w-4" />
            <span className="text-sm">{t('dashboard.netPnl')}</span>
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
          {t('dashboard.capitalPaper')}
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
                          realized_pnl_usdt: s.account.realized_pnl_usdt,
                          unrealized_pnl_usdt: s.account.unrealized_pnl_usdt,
                          open_positions_count: s.open_positions_count ?? 0,
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
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8">
              <div className="rounded-lg border border-white/5 bg-black/20 p-3">
                <p className="text-xs text-[var(--text-muted)]">{t('dashboard.initialCapital')}</p>
                <p className="text-lg font-semibold">${parseFloat(accountSummary.initial_balance_usdt).toFixed(2)}</p>
              </div>
              <div className="rounded-lg border border-white/5 bg-black/20 p-3">
                <p className="text-xs text-[var(--text-muted)]">{t('dashboard.currentBalance')}</p>
                <p className="text-lg font-semibold">${parseFloat(accountSummary.current_balance_usdt).toFixed(2)}</p>
              </div>
              <div className="rounded-lg border border-white/5 bg-black/20 p-3">
                <p className="text-xs text-[var(--text-muted)]">{t('dashboard.equity')}</p>
                <p className="text-lg font-semibold">
                  ${accountSummary.equity_usdt != null ? parseFloat(accountSummary.equity_usdt).toFixed(2) : parseFloat(accountSummary.current_balance_usdt).toFixed(2)}
                </p>
              </div>
              <div className="rounded-lg border border-white/5 bg-black/20 p-3">
                <p className="text-xs text-[var(--text-muted)]">{t('dashboard.availableCapital')}</p>
                <p className="text-lg font-semibold">${parseFloat(accountSummary.available_balance_usdt).toFixed(2)}</p>
              </div>
              <div className="rounded-lg border border-white/5 bg-black/20 p-3">
                <p className="text-xs text-[var(--text-muted)]">{t('dashboard.usedMargin')}</p>
                <p className="text-lg font-semibold">${parseFloat(accountSummary.used_margin_usdt).toFixed(2)}</p>
              </div>
              <div className="rounded-lg border border-white/5 bg-black/20 p-3">
                <p className="text-xs text-[var(--text-muted)]">{t('dashboard.realizedPnl')}</p>
                <p className={`text-lg font-semibold ${parseFloat(accountSummary.realized_pnl_usdt ?? '0') >= 0 ? 'text-[var(--positive)]' : 'text-[var(--negative)]'}`}>
                  ${parseFloat(accountSummary.realized_pnl_usdt ?? '0').toFixed(2)}
                </p>
              </div>
              <div className="rounded-lg border border-white/5 bg-black/20 p-3">
                <p className="text-xs text-[var(--text-muted)]">{t('dashboard.unrealizedPnl')}</p>
                <p className={`text-lg font-semibold ${parseFloat(accountSummary.unrealized_pnl_usdt ?? '0') >= 0 ? 'text-[var(--positive)]' : 'text-[var(--negative)]'}`}>
                  ${parseFloat(accountSummary.unrealized_pnl_usdt ?? '0').toFixed(2)}
                </p>
              </div>
              <div className="rounded-lg border border-white/5 bg-black/20 p-3">
                <p className="text-xs text-[var(--text-muted)]">{t('dashboard.feesAccumulated')}</p>
                <p className="text-lg font-semibold">${parseFloat(accountSummary.total_fees_usdt).toFixed(2)}</p>
              </div>
              <div className="rounded-lg border border-white/5 bg-black/20 p-3">
                <p className="text-xs text-[var(--text-muted)]">{t('dashboard.openPositions')}</p>
                <p className="text-lg font-semibold">{accountSummary.open_positions_count ?? 0}</p>
              </div>
            </div>
          ) : (
            <p className="text-sm text-[var(--text-muted)]">
              {loading ? t('dashboard.loadingAccount') : t('dashboard.noAccount')}
            </p>
          )}
        </div>

      {/* Estado del sistema: scheduler, supervisor, última sync velas, última estrategia */}
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-4">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-[var(--text-muted)]">
            <Activity className="h-4 w-4" />
            {t('dashboard.scheduler')}
          </h3>
          {schedulerStatus ? (
            <div className="space-y-1 text-sm">
              <p>
                <span className="text-[var(--text-muted)]">{t('dashboard.status')}: </span>
                <span className={schedulerStatus.running ? 'text-green-500' : 'text-amber-500'}>
                  {schedulerStatus.running ? t('dashboard.active') : t('dashboard.inactive')}
                </span>
              </p>
              {schedulerStatus.started_at != null && (
                <p className="text-[var(--text-muted)]">{t('dashboard.startedAt')}: {format(new Date(schedulerStatus.started_at * 1000), 'HH:mm:ss')}</p>
              )}
              {(['15m', '30m', '1h'] as const).map((tf) => {
                const jobKeySync = `sync_candles_${tf}` as keyof typeof schedulerStatus.jobs
                const jobKeyStrats = `run_strategies_${tf}` as keyof typeof schedulerStatus.jobs
                const syncJob = schedulerStatus.jobs?.[jobKeySync] as { last_run_at?: number; last_error?: string } | undefined
                const stratJob = schedulerStatus.jobs?.[jobKeyStrats] as { last_run_at?: number } | undefined
                return (
                  <div key={tf} className="flex flex-wrap gap-x-3 gap-y-0.5 text-sm">
                    {syncJob?.last_run_at != null && (
                      <span className="text-[var(--text-muted)]">{t('dashboard.lastSync')} {tf}: {format(new Date(syncJob.last_run_at * 1000), 'HH:mm:ss')}</span>
                    )}
                    {stratJob?.last_run_at != null && (
                      <span className="text-[var(--text-muted)]">{t('dashboard.lastStrategy')} {tf}: {format(new Date(stratJob.last_run_at * 1000), 'HH:mm:ss')}</span>
                    )}
                  </div>
                )
              })}
              {schedulerStatus.jobs?.sync_candles_15m?.last_error != null && (
                <p className="text-amber-400 text-xs mt-1" title={schedulerStatus.jobs.sync_candles_15m.last_error}>
                  {t('dashboard.syncCandlesError')}: {schedulerStatus.jobs.sync_candles_15m.last_error.slice(0, 60)}{schedulerStatus.jobs.sync_candles_15m.last_error.length > 60 ? '…' : ''}
                </p>
              )}
            </div>
          ) : (
            <p className="text-sm text-[var(--text-muted)]">{t('dashboard.notAvailableBackend')}</p>
          )}
        </div>
        <div className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-4">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-[var(--text-muted)]">
            <Bot className="h-4 w-4" />
            {t('dashboard.supervisor')}
          </h3>
          {supervisorStatus ? (
            <div className="space-y-1 text-sm">
              <p>
                <span className="text-[var(--text-muted)]">{t('dashboard.status')}: </span>
                <span className={supervisorStatus.running ? 'text-green-500' : 'text-amber-500'}>
                  {supervisorStatus.running ? t('dashboard.active') : t('dashboard.inactive')}
                </span>
              </p>
              <p className="text-[var(--text-muted)]">
                {t('dashboard.cycleEvery')} {supervisorStatus.check_interval_seconds} s
                {supervisorStatus.last_cycle_at != null && (
                  <> · {t('dashboard.last')}: {format(new Date(supervisorStatus.last_cycle_at * 1000), 'HH:mm:ss')}</>
                )}
              </p>
            </div>
          ) : (
            <p className="text-sm text-[var(--text-muted)]">{t('dashboard.notAvailable')}</p>
          )}
        </div>
        <div className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-4">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-[var(--text-muted)]">
            <FileText className="h-4 w-4" />
            {t('dashboard.botLogs')}
          </h3>
          <div className="max-h-32 overflow-y-auto space-y-1 text-xs">
            {botLogs.length === 0 && <p className="text-[var(--text-muted)]">{t('dashboard.noLogs')}</p>}
            {botLogs.map((log) => (
              <div key={log.id} className="flex flex-wrap gap-1 border-b border-white/5 py-0.5 items-center">
                <span className="text-[var(--text-muted)] shrink-0">{format(new Date(log.created_at), 'HH:mm:ss')}</span>
                <button
                  type="button"
                  onClick={() => setEventTypeForHelp(log.event_type)}
                  className={log.level === 'ERROR' ? 'text-red-400 hover:underline' : log.level === 'WARN' ? 'text-amber-400 hover:underline' : 'text-[var(--accent)] hover:underline'}
                  title={getEventExplanation(log.event_type) ? t('dashboard.clickToExplain') : undefined}
                >
                  [{log.event_type}]
                </button>
                <span className="truncate">{log.message}</span>
              </div>
            ))}
          </div>
          {eventTypeForHelp != null && (
            <EventExplanationModal eventType={eventTypeForHelp} onClose={() => setEventTypeForHelp(null)} />
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-xl border border-white/10 bg-[var(--surface-muted)] p-4">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-[var(--text-muted)]">{t('dashboard.candles')}</h3>
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-xs text-[var(--text-muted)]">{t('dashboard.indicatorsOverlay')}:</span>
              {(['breakout', 'vwap_snapback', 'ema_pullback'] as const).map((id) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setStrategyOverlay(strategyOverlay === id ? null : id)}
                  title={t(`dashboard.indicatorsTooltip.${id}`)}
                  className={`rounded-lg border px-2.5 py-1 text-xs font-medium transition-colors ${
                    strategyOverlay === id
                      ? 'border-[var(--accent)] bg-[var(--accent)]/20 text-[var(--accent)]'
                      : 'border-white/10 bg-white/5 text-[var(--text-muted)] hover:bg-white/10 hover:text-[var(--text)]'
                  }`}
                >
                  {t(`dashboard.strategyOverlay.${id}`)}
                </button>
              ))}
              {strategyOverlay && (
                <button
                  type="button"
                  onClick={() => setStrategyOverlay(null)}
                  title={t('dashboard.indicatorsTooltip.none')}
                  className="rounded-lg border border-white/10 bg-white/5 px-2.5 py-1 text-xs font-medium text-[var(--text-muted)] hover:bg-white/10 hover:text-[var(--text)]"
                >
                  {t('dashboard.strategyOverlay.none')}
                </button>
              )}
            </div>
          </div>
          {loading ? (
            <div className="flex h-[400px] items-center justify-center text-[var(--text-muted)]">{t('dashboard.loadingChart')}</div>
          ) : candlesError || candles.length === 0 ? (
            <div className="flex h-[400px] flex-col items-center justify-center gap-3 rounded-lg border border-white/10 bg-black/20 p-6 text-center">
              <p className="text-[var(--text-muted)]">
                {candlesError ?? t('dashboard.noCandles')}
              </p>
              <p className="text-xs text-[var(--text-muted)]">
                {t('dashboard.checkBackendCandles')}
              </p>
              <button
                type="button"
                onClick={() => {
                  setCandlesError(null)
                  setLoading(true)
                  fetchKlines('BTCUSDT', interval, 300)
                    .then((res) => {
                      setCandles(res.candles)
                      setCandlesError(null)
                      if (res.source) setMarketDataSource(res.source)
                    })
                    .catch((err: Error) => setCandlesError(err?.message ?? 'Error'))
                    .finally(() => setLoading(false))
                }}
                className="rounded-lg border border-[var(--accent)] bg-[var(--accent)]/20 px-4 py-2 text-sm font-medium text-[var(--accent)] hover:bg-[var(--accent)]/30"
              >
                {t('dashboard.retryCandles')}
              </button>
            </div>
          ) : (
            <CandlestickChart
              data={candles}
              interval={interval}
              onCrosshairMove={setCrosshairPrice}
              livePrice={livePrice}
              strategyOverlay={strategyOverlay}
              indicatorName={strategyOverlay ? t(`dashboard.strategyOverlay.${strategyOverlay}`) : undefined}
              indicatorDescription={strategyOverlay ? t(`dashboard.indicatorsTooltip.${strategyOverlay}`) : undefined}
            />
          )}
        </div>
        <div className="space-y-4">
          <div className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-4">
            <h3 className="mb-3 text-sm font-semibold text-[var(--text-muted)]">{t('dashboard.feesPaid')}</h3>
            <p className="text-xl font-bold">${metrics?.total_fees != null ? parseFloat(metrics.total_fees).toFixed(2) : '0.00'}</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-4">
            <h3 className="mb-3 text-sm font-semibold text-[var(--text-muted)]">{t('dashboard.profitFactor')}</h3>
            <p className="text-xl font-bold">{metrics?.profit_factor != null ? metrics.profit_factor.toFixed(2) : '—'}</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-4">
            <h3 className="mb-3 text-sm font-semibold text-[var(--text-muted)]">{t('dashboard.pnlByStrategy')}</h3>
            <ul className="space-y-2">
              {(metrics?.pnl_by_strategy ?? []).map((s) => (
                <li key={s.strategy_name} className="flex justify-between text-sm">
                  <span className="text-[var(--text-muted)]">{s.strategy_name}</span>
                  <span className={s.net_pnl >= 0 ? 'text-[var(--positive)]' : 'text-[var(--negative)]'}>
                    ${s.net_pnl.toFixed(2)}
                  </span>
                </li>
              ))}
              {(!metrics?.pnl_by_strategy?.length) && <li className="text-sm text-[var(--text-muted)]">{t('dashboard.noDataStrategy')}</li>}
            </ul>
          </div>
          <div className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-4">
            <h3 className="mb-3 text-sm font-semibold text-[var(--text-muted)]">{t('dashboard.pnlByLeverage')}</h3>
            <ul className="space-y-2">
              {(metrics?.pnl_by_leverage ?? []).map((l) => (
                <li key={l.leverage} className="flex justify-between text-sm">
                  <span className="text-[var(--text-muted)]">x{l.leverage}</span>
                  <span className={l.net_pnl >= 0 ? 'text-[var(--positive)]' : 'text-[var(--negative)]'}>
                    ${l.net_pnl.toFixed(2)}
                  </span>
                </li>
              ))}
              {(!metrics?.pnl_by_leverage?.length) && <li className="text-sm text-[var(--text-muted)]">{t('dashboard.noDataLeverage')}</li>}
            </ul>
          </div>
        </div>
      </div>

      {/* Historial reciente en la parte inferior */}
      <div className="rounded-xl border border-white/10 bg-[var(--surface-muted)] p-4">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-[var(--text-muted)]">
            <History className="h-4 w-4" />
            {t('dashboard.recentHistory')}
          </h3>
          <Link
            to="/history"
            className="flex items-center gap-1 rounded-lg border border-white/10 px-3 py-1.5 text-sm font-medium hover:bg-white/5"
          >
            {t('dashboard.viewAll')}
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
                    {t('dashboard.noOperations')} <Link to="/trade" className="text-[var(--accent)] hover:underline">{t('dashboard.newTradeLink')}</Link>
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
