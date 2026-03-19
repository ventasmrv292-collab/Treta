export interface PaperAccount {
  id: number
  name: string
  base_currency: string
  initial_balance_usdt: string
  current_balance_usdt: string
  available_balance_usdt: string
  used_margin_usdt: string
  realized_pnl_usdt: string
  unrealized_pnl_usdt: string
  total_fees_usdt: string
  status: string
}

export interface DashboardSummary {
  btc_price?: string | null
  total_trades: number
  win_rate: number
  net_pnl: string
  gross_pnl: string
  total_fees: string
  profit_factor: number
  pnl_by_strategy: { strategy_name: string; strategy_family: string; net_pnl: number }[]
  pnl_by_leverage: { leverage: number; net_pnl: number }[]
  account?: PaperAccount | null
  equity_usdt?: string | null
  open_positions_count?: number
}

export interface Trade {
  id: number
  source: string
  symbol: string
  market: string
  strategy_family: string
  strategy_name: string
  strategy_version: string
  timeframe: string
  position_side: string
  order_side_entry: string
  order_type_entry: string
  maker_taker_entry: string | null
  leverage: number
  quantity: string
  entry_price: string
  take_profit: string | null
  stop_loss: string | null
  signal_timestamp: string | null
  strategy_params_json: string | null
  notes: string | null
  exit_price: string | null
  exit_order_type: string | null
  maker_taker_exit: string | null
  exit_reason: string | null
  closed_at: string | null
  entry_notional: string | null
  exit_notional: string | null
  entry_fee: string | null
  exit_fee: string | null
  funding_fee: string | null
  slippage_usdt: string | null
  gross_pnl_usdt: string | null
  net_pnl_usdt: string | null
  pnl_pct_notional: string | null
  pnl_pct_margin: string | null
  created_at: string
  updated_at: string
  account_id?: number | null
  status?: string
  /** Estado de la señal asociada: RECEIVED, ACCEPTED, PENDING_ORDER, STALE, EXPIRED, REJECTED */
  signal_event_status?: string | null
  opened_at?: string
  margin_used_usdt?: string | null
  capital_before_usdt?: string | null
  capital_after_usdt?: string | null
  risk_profile_id?: number | null
}

export interface TradeListResponse {
  items: Trade[]
  total: number
  page: number
  size: number
  pages: number
}

export interface Strategy {
  id: number
  family: string
  name: string
  version: string
  description: string | null
  default_params_json: string | null
  active: boolean
  created_at: string
  updated_at: string
}

export interface DashboardMetrics {
  total_trades: number
  winning_trades: number
  losing_trades: number
  win_rate: number
  gross_pnl: string
  net_pnl: string
  total_fees: string
  profit_factor: number
  pnl_by_strategy: { strategy_name: string; strategy_family: string; net_pnl: number }[]
  pnl_by_leverage: { leverage: number; net_pnl: number }[]
}

export interface CandleData {
  time: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface KlinesResponse {
  symbol: string
  interval: string
  /** Fuente de los datos: binance, bybit, coingecko */
  source?: string
  candles: CandleData[]
}

export interface MarketRegimeStatus {
  symbol: string
  requested_timeframe: string
  current_regime: {
    regime: string
    reason: string
    cooldown_active: boolean
    cooldown_bars_remaining: number
    raw_regime: string
    timeframe_used: string
  }
  regimes_by_timeframe: Record<string, {
    regime: string
    reason: string
    cooldown_active: boolean
    cooldown_bars_remaining: number
    raw_regime: string
    timeframe_used: string
  }>
  strategy_long_permissions: {
    strategy_family: string
    strategy_name: string
    strategy_version: string
    strategy_timeframe: string
    regime_timeframe_used: string
    long_allowed: boolean
    long_reason: string
    market_regime: string
  }[]
}

export interface ManualTradeCreate {
  source: 'manual'
  symbol: string
  market: string
  strategy_family: string
  strategy_name: string
  strategy_version: string
  timeframe: string
  position_side: 'LONG' | 'SHORT'
  order_side_entry: 'BUY' | 'SELL'
  order_type_entry: 'MARKET' | 'LIMIT'
  maker_taker_entry: 'MAKER' | 'TAKER'
  leverage: number
  quantity: string
  entry_price: string
  take_profit?: string | null
  stop_loss?: string | null
  notes?: string | null
  account_id?: number | null
  fee_config_id?: number | null
  risk_profile_id?: number | null
}

export interface RiskProfile {
  id: number
  name: string
  sizing_mode: string
  fixed_quantity: string | null
  fixed_notional_usdt: string | null
  risk_pct_per_trade: string | null
  max_open_positions: number
  max_margin_pct_of_account: string
  max_daily_loss_usdt: string | null
  max_daily_loss_pct: string | null
  cooldown_after_losses: number | null
  allowed_leverage_json: string | null
  created_at: string
  updated_at: string
}

export interface PositionSizePreview {
  quantity: string
  entry_notional: string
  margin_used_usdt: string
  entry_fee_estimate: string
  estimated_loss_to_sl_usdt: string | null
}

export interface BotLogEntry {
  id: number
  level: string
  module: string
  event_type: string
  message: string
  context_json: string | null
  related_trade_id: number | null
  related_signal_event_id: number | null
  created_at: string
}

/** Señal: RECEIVED, ACCEPTED, PENDING_ORDER, STALE, EXPIRED, REJECTED */
export interface SignalEventRow {
  id: number
  source: string
  symbol: string
  timeframe: string
  strategy_family: string
  strategy_name: string
  strategy_version: string
  status: string
  decision_reason: string | null
  trade_id: number | null
  created_at: string | null
  processed_at: string | null
}

export interface SupervisorStatus {
  running: boolean
  last_cycle_at: number | null
  check_interval_seconds: number
}

export interface TradeClosePayload {
  exit_price: string
  exit_order_type: string
  maker_taker_exit: string
  exit_reason: string
  closed_at?: string | null
}

export interface BacktestRun {
  id: number
  strategy_family: string
  strategy_name: string
  strategy_version: string
  symbol: string
  interval: string
  start_time: string
  end_time: string
  initial_capital: string
  leverage: number
  fee_profile: string
  slippage_bps: number
  status: string
  total_trades: number | null
  net_pnl: string | null
  gross_pnl: string | null
  total_fees: string | null
  win_rate: number | null
  profit_factor: number | null
  max_drawdown_pct: number | null
  created_at: string
  final_capital?: string | null
  peak_equity?: string | null
  min_equity?: string | null
}

export interface BacktestEquityPoint {
  point_time: string
  equity_usdt: string
  balance_usdt: string
  used_margin_usdt: string
  drawdown_pct: string
}
