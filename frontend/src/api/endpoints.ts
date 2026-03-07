import { API_BASE, USE_SUPABASE, SUPABASE_URL, SUPABASE_ANON_KEY } from '../config'
import type {
  Trade,
  TradeListResponse,
  Strategy,
  DashboardMetrics,
  DashboardSummary,
  PaperAccount,
  KlinesResponse,
  ManualTradeCreate,
  TradeClosePayload,
  BacktestRun,
  RiskProfile,
  PositionSizePreview,
  BotLogEntry,
  SupervisorStatus,
} from '../types'

const API_V1 = `${API_BASE}/api/v1`

function supabaseFetch(path: string, options: RequestInit = {}) {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) throw new Error('Supabase no configurado')
  const url = path.startsWith('http') ? path : `${SUPABASE_URL}${path}`
  const headers: Record<string, string> = {
    Authorization: `Bearer ${SUPABASE_ANON_KEY}`,
    apikey: SUPABASE_ANON_KEY,
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }
  return fetch(url, { ...options, headers })
}

const qs = (params: Record<string, string | number | boolean | undefined>) => {
  const s = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== '') s.set(k, String(v))
  })
  const str = s.toString()
  return str ? `?${str}` : ''
}

export const endpoints = {
  market: {
    price: (symbol = 'BTCUSDT') => `/market/price${qs({ symbol })}`,
    klines: (symbol = 'BTCUSDT', interval = '15m', limit = 300) =>
      `/market/klines${qs({ symbol, interval, limit })}`,
  },
  trades: {
    list: (params: {
      page?: number
      size?: number
      symbol?: string
      strategy_family?: string
      strategy_name?: string
      source?: string
      position_side?: string
      leverage?: number
      closed_only?: boolean
      winners_only?: boolean
      losers_only?: boolean
      date_from?: string
      date_to?: string
    }) => `/trades${qs(params as Record<string, string | number | boolean | undefined>)}`,
    get: (id: number) => `/trades/${id}`,
    create: () => '/trades',
    close: (id: number) => `/trades/${id}/close`,
  },
  strategies: {
    list: () => '/strategies',
    get: (id: number) => `/strategies/${id}`,
  },
  paperAccounts: {
    list: () => '/paper-accounts',
    get: (id: number) => `/paper-accounts/${id}`,
  },
  analytics: {
    dashboard: () => '/analytics/dashboard',
    dashboardSummary: (accountId?: number) =>
      accountId != null ? `/analytics/dashboard-summary${qs({ account_id: accountId })}` : '/analytics/dashboard-summary',
    byStrategy: () => '/analytics/by-strategy',
    byLeverage: () => '/analytics/by-leverage',
    equityCurve: (period?: string) => `/analytics/equity-curve${qs({ period: period || 'all' })}`,
  },
  backtest: {
    list: () => '/backtest',
    run: () => '/backtest',
    get: (id: number) => `/backtest/${id}`,
  },
  webhook: {
    n8n: () => '/webhook/n8n/trade',
  },
  riskProfiles: {
    list: () => '/risk-profiles',
    get: (id: number) => `/risk-profiles/${id}`,
    positionSizePreview: (profileId: number, params: { entry_price: string; leverage?: number; stop_loss?: string; position_side?: string; account_id?: number }) =>
      `/risk-profiles/${profileId}/position-size-preview${qs(params as Record<string, string | number | undefined>)}`,
  },
  botLogs: {
    list: (params?: { limit?: number; event_type?: string; module?: string }) =>
      `/bot-logs${qs(params || {})}`,
  },
  supervisor: {
    status: () => '/supervisor/status',
  },
}

export async function fetchPrice(symbol: string) {
  const res = await fetch(`${API_V1}${endpoints.market.price(symbol)}`)
  if (!res.ok) throw new Error('Failed to fetch price')
  return res.json() as Promise<{ symbol: string; price: string }>
}

export async function fetchKlines(symbol: string, interval: string, limit = 300) {
  const res = await fetch(`${API_V1}${endpoints.market.klines(symbol, interval, limit)}`)
  if (!res.ok) throw new Error('Failed to fetch klines')
  return res.json() as Promise<KlinesResponse>
}

export async function fetchTrades(params: Parameters<typeof endpoints.trades.list>[0]) {
  if (USE_SUPABASE) {
    const page = params?.page ?? 1
    const size = params?.size ?? 20
    const from = (page - 1) * size
    const searchParams = new URLSearchParams()
    searchParams.set('select', '*')
    searchParams.set('order', 'created_at.desc')
    searchParams.set('offset', String(from))
    searchParams.set('limit', String(size))
    if (params?.symbol) searchParams.set('symbol', `eq.${params.symbol}`)
    if (params?.strategy_family) searchParams.set('strategy_family', `eq.${params.strategy_family}`)
    if (params?.strategy_name) searchParams.set('strategy_name', `eq.${params.strategy_name}`)
    if (params?.source) searchParams.set('source', `eq.${params.source}`)
    if (params?.position_side) searchParams.set('position_side', `eq.${params.position_side}`)
    if (params?.leverage != null) searchParams.set('leverage', `eq.${params.leverage}`)
    if (params?.closed_only) searchParams.set('closed_at', 'not.is.null')
    const res = await supabaseFetch(`/rest/v1/trades?${searchParams}`, {
      headers: { Prefer: 'count=exact' },
    })
    if (!res.ok) throw new Error('Failed to fetch trades')
    const items = (await res.json()) as Trade[]
    const contentRange = res.headers.get('Content-Range')
    const total = contentRange ? parseInt(contentRange.split('/')[1] ?? String(items.length), 10) : items.length
    let filtered = items
    if (params?.winners_only) filtered = items.filter((t) => t.net_pnl_usdt != null && Number(t.net_pnl_usdt) > 0)
    if (params?.losers_only) filtered = items.filter((t) => t.net_pnl_usdt != null && Number(t.net_pnl_usdt) < 0)
    const pages = Math.ceil(total / size) || 1
    return { items: filtered, total, page, size, pages } as TradeListResponse
  }
  const res = await fetch(`${API_V1}${endpoints.trades.list(params)}`)
  if (!res.ok) throw new Error('Failed to fetch trades')
  return res.json() as Promise<TradeListResponse>
}

export async function fetchDashboard() {
  const res = await fetch(`${API_V1}${endpoints.analytics.dashboard()}`)
  if (!res.ok) throw new Error('Failed to fetch dashboard')
  return res.json() as Promise<DashboardMetrics>
}

/** Analíticas (by-strategy, by-leverage, equity-curve). Con Supabase usa la Edge Function get-analytics. */
export async function fetchAnalytics(): Promise<{
  byStrategy: { strategy_name: string; strategy_family: string; total_trades: number; net_pnl: string; gross_pnl: string; total_fees: string; win_rate: number; profit_factor: number; avg_win: string; avg_loss: string; expectancy: string }[]
  byLeverage: { leverage: number; total_trades: number; net_pnl: string; win_rate: number; total_fees: string }[]
  equityCurve: { points: { time: string | null; equity: number }[] }
}> {
  if (USE_SUPABASE) {
    const res = await supabaseFetch('/functions/v1/get-analytics')
    if (!res.ok) throw new Error('Failed to fetch analytics')
    const data = await res.json()
    return {
      byStrategy: data.byStrategy ?? [],
      byLeverage: data.byLeverage ?? [],
      equityCurve: data.equityCurve ?? { points: [] },
    }
  }
  const [byStrategy, byLeverage, equityCurve] = await Promise.all([
    fetch(`${API_V1}${endpoints.analytics.byStrategy()}`).then((r) => r.json()),
    fetch(`${API_V1}${endpoints.analytics.byLeverage()}`).then((r) => r.json()),
    fetch(`${API_V1}${endpoints.analytics.equityCurve()}`).then((r) => r.json()),
  ])
  return { byStrategy, byLeverage, equityCurve }
}

export async function fetchPaperAccounts() {
  if (USE_SUPABASE) {
    const res = await supabaseFetch('/rest/v1/paper_accounts?select=*&order=id')
    if (!res.ok) throw new Error('Failed to fetch paper accounts')
    return res.json() as Promise<PaperAccount[]>
  }
  const res = await fetch(`${API_V1}${endpoints.paperAccounts.list()}`)
  if (!res.ok) throw new Error('Failed to fetch paper accounts')
  return res.json() as Promise<PaperAccount[]>
}

export async function fetchDashboardSummary(accountId?: number) {
  if (USE_SUPABASE) {
    const q = accountId != null ? `?account_id=${accountId}` : ''
    const res = await supabaseFetch(`/functions/v1/get-dashboard-summary${q}`)
    if (!res.ok) throw new Error('Failed to fetch dashboard summary')
    return res.json() as Promise<DashboardSummary>
  }
  const res = await fetch(`${API_V1}${endpoints.analytics.dashboardSummary(accountId)}`)
  if (!res.ok) throw new Error('Failed to fetch dashboard summary')
  return res.json() as Promise<DashboardSummary>
}

export async function fetchStrategies() {
  if (USE_SUPABASE) {
    const res = await supabaseFetch('/rest/v1/strategies?select=*&order=id')
    if (!res.ok) throw new Error('Failed to fetch strategies')
    return res.json() as Promise<Strategy[]>
  }
  const res = await fetch(`${API_V1}${endpoints.strategies.list()}`)
  if (!res.ok) throw new Error('Failed to fetch strategies')
  return res.json() as Promise<Strategy[]>
}

export async function createTrade(payload: ManualTradeCreate) {
  if (USE_SUPABASE) {
    const res = await supabaseFetch('/functions/v1/create-manual-trade', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error((err as { error?: string }).error || 'Failed to create trade')
    }
    return res.json() as Promise<Trade>
  }
  const res = await fetch(`${API_V1}${endpoints.trades.create()}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { detail?: string }).detail || 'Failed to create trade')
  }
  return res.json() as Promise<Trade>
}

export async function closeTrade(id: number, payload: TradeClosePayload) {
  if (USE_SUPABASE) {
    const res = await supabaseFetch('/functions/v1/close-trade', {
      method: 'POST',
      body: JSON.stringify({ trade_id: id, ...payload }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error((err as { error?: string }).error || 'Failed to close trade')
    }
    return res.json() as Promise<Trade>
  }
  const res = await fetch(`${API_V1}${endpoints.trades.close(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { detail?: string }).detail || 'Failed to close trade')
  }
  return res.json() as Promise<Trade>
}

export async function runBacktest(payload: {
  strategy_family: string
  strategy_name: string
  strategy_version: string
  symbol?: string
  interval?: string
  start_time: string
  end_time: string
  initial_capital: string
  leverage?: number
  fee_profile?: string
  slippage_bps?: number
}) {
  if (USE_SUPABASE) {
    const res = await supabaseFetch('/functions/v1/run-backtest', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error((err as { error?: string }).error || 'Backtest failed')
    }
    return res.json() as Promise<BacktestRun>
  }
  const res = await fetch(`${API_V1}${endpoints.backtest.run()}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { detail?: string }).detail || 'Backtest failed')
  }
  return res.json() as Promise<BacktestRun>
}

export async function fetchRiskProfiles() {
  const res = await fetch(`${API_V1}${endpoints.riskProfiles.list()}`)
  if (!res.ok) throw new Error('Failed to fetch risk profiles')
  return res.json() as Promise<RiskProfile[]>
}

export async function fetchPositionSizePreview(
  profileId: number,
  params: { entry_price: string; leverage?: number; stop_loss?: string; position_side?: string; account_id?: number }
) {
  const q = new URLSearchParams()
  q.set('entry_price', params.entry_price)
  if (params.leverage != null) q.set('leverage', String(params.leverage))
  if (params.stop_loss) q.set('stop_loss', params.stop_loss)
  if (params.position_side) q.set('position_side', params.position_side)
  if (params.account_id != null) q.set('account_id', String(params.account_id))
  const res = await fetch(`${API_V1}/risk-profiles/${profileId}/position-size-preview?${q}`)
  if (!res.ok) throw new Error('Failed to fetch position size preview')
  return res.json() as Promise<PositionSizePreview>
}

export async function fetchBotLogs(params?: { limit?: number; event_type?: string; module?: string }) {
  const q = new URLSearchParams()
  if (params?.limit) q.set('limit', String(params.limit))
  if (params?.event_type) q.set('event_type', params.event_type)
  if (params?.module) q.set('module', params.module)
  const res = await fetch(`${API_V1}/bot-logs?${q}`)
  if (!res.ok) throw new Error('Failed to fetch bot logs')
  return res.json() as Promise<BotLogEntry[]>
}

export async function fetchSupervisorStatus() {
  const res = await fetch(`${API_V1}${endpoints.supervisor.status()}`)
  if (!res.ok) throw new Error('Failed to fetch supervisor status')
  return res.json() as Promise<SupervisorStatus>
}
