import { API_BASE } from '../config'
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
} from '../types'

const API_V1 = `${API_BASE}/api/v1`

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
  const res = await fetch(`${API_V1}${endpoints.trades.list(params)}`)
  if (!res.ok) throw new Error('Failed to fetch trades')
  return res.json() as Promise<TradeListResponse>
}

export async function fetchDashboard() {
  const res = await fetch(`${API_V1}${endpoints.analytics.dashboard()}`)
  if (!res.ok) throw new Error('Failed to fetch dashboard')
  return res.json() as Promise<DashboardMetrics>
}

export async function fetchPaperAccounts() {
  const res = await fetch(`${API_V1}${endpoints.paperAccounts.list()}`)
  if (!res.ok) throw new Error('Failed to fetch paper accounts')
  return res.json() as Promise<PaperAccount[]>
}

export async function fetchDashboardSummary(accountId?: number) {
  const res = await fetch(`${API_V1}${endpoints.analytics.dashboardSummary(accountId)}`)
  if (!res.ok) throw new Error('Failed to fetch dashboard summary')
  return res.json() as Promise<DashboardSummary>
}

export async function fetchStrategies() {
  const res = await fetch(`${API_V1}${endpoints.strategies.list()}`)
  if (!res.ok) throw new Error('Failed to fetch strategies')
  return res.json() as Promise<Strategy[]>
}

export async function createTrade(payload: ManualTradeCreate) {
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
