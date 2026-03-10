-- ============================================================
-- Vistas de analíticas avanzadas: por estrategia, timeframe, side, perfil
-- ============================================================

-- A) Por estrategia + timeframe + side
CREATE OR REPLACE VIEW public.analytics_by_strategy_tf_side AS
SELECT
  strategy_family,
  strategy_name,
  strategy_version,
  timeframe,
  position_side,
  COUNT(*)::int AS total_trades,
  COUNT(*) FILTER (WHERE status = 'CLOSED')::int AS closed_trades,
  COUNT(*) FILTER (WHERE status = 'OPEN')::int AS open_trades,
  COALESCE(SUM(gross_pnl_usdt), 0) AS gross_pnl,
  COALESCE(SUM(net_pnl_usdt), 0) AS net_pnl,
  COALESCE(SUM(COALESCE(entry_fee,0) + COALESCE(exit_fee,0)), 0) AS total_fees,
  COALESCE(AVG(net_pnl_usdt) FILTER (WHERE status = 'CLOSED'), 0) AS avg_pnl,
  ROUND(
    (COUNT(*) FILTER (WHERE net_pnl_usdt > 0)::numeric / NULLIF(COUNT(*) FILTER (WHERE status = 'CLOSED'), 0) * 100)::numeric,
    2
  ) AS win_rate,
  COALESCE(AVG(net_pnl_usdt) FILTER (WHERE net_pnl_usdt > 0), 0) AS avg_win,
  COALESCE(AVG(net_pnl_usdt) FILTER (WHERE net_pnl_usdt < 0), 0) AS avg_loss,
  ROUND(
    (COALESCE(SUM(net_pnl_usdt) FILTER (WHERE net_pnl_usdt > 0), 0) /
     NULLIF(ABS(COALESCE(SUM(net_pnl_usdt) FILTER (WHERE net_pnl_usdt < 0), 0)), 0))::numeric,
    4
  ) AS profit_factor
FROM public.trades
WHERE closed_at IS NOT NULL AND net_pnl_usdt IS NOT NULL
GROUP BY strategy_family, strategy_name, strategy_version, timeframe, position_side;

-- B) Por timeframe
CREATE OR REPLACE VIEW public.analytics_by_timeframe AS
SELECT
  timeframe,
  COUNT(*)::int AS total_trades,
  COUNT(*) FILTER (WHERE status = 'CLOSED')::int AS closed_trades,
  COALESCE(SUM(net_pnl_usdt), 0) AS net_pnl,
  ROUND(
    (COUNT(*) FILTER (WHERE net_pnl_usdt > 0)::numeric / NULLIF(COUNT(*) FILTER (WHERE status = 'CLOSED'),0) * 100)::numeric,
    2
  ) AS win_rate
FROM public.trades
WHERE closed_at IS NOT NULL AND net_pnl_usdt IS NOT NULL
GROUP BY timeframe;

-- C) Por side (LONG vs SHORT)
CREATE OR REPLACE VIEW public.analytics_by_side AS
SELECT
  position_side,
  COUNT(*)::int AS total_trades,
  COUNT(*) FILTER (WHERE status = 'CLOSED')::int AS closed_trades,
  COALESCE(SUM(net_pnl_usdt), 0) AS net_pnl,
  ROUND(
    (COUNT(*) FILTER (WHERE net_pnl_usdt > 0)::numeric / NULLIF(COUNT(*) FILTER (WHERE status = 'CLOSED'),0) * 100)::numeric,
    2
  ) AS win_rate
FROM public.trades
WHERE closed_at IS NOT NULL AND net_pnl_usdt IS NOT NULL
GROUP BY position_side;

-- D) Por risk_profile y fee_config
CREATE OR REPLACE VIEW public.analytics_by_profile AS
SELECT
  risk_profile_id,
  fee_config_id,
  COUNT(*)::int AS total_trades,
  COALESCE(SUM(net_pnl_usdt), 0) AS net_pnl,
  ROUND(
    (COUNT(*) FILTER (WHERE net_pnl_usdt > 0)::numeric / NULLIF(COUNT(*) FILTER (WHERE status = 'CLOSED'),0) * 100)::numeric,
    2
  ) AS win_rate
FROM public.trades
WHERE closed_at IS NOT NULL AND net_pnl_usdt IS NOT NULL
GROUP BY risk_profile_id, fee_config_id;
