-- ============================================================
-- Vistas y función RPC para Analíticas (trades cerrados)
-- Fuente: public.trades (closed_at NOT NULL, net_pnl_usdt NOT NULL)
-- ============================================================

-- A) Vista: analytics_by_strategy
CREATE OR REPLACE VIEW public.analytics_by_strategy AS
SELECT
  strategy_family,
  strategy_name,
  COUNT(*)::int AS total_trades,
  COALESCE(SUM(net_pnl_usdt), 0) AS total_net_pnl,
  COALESCE(AVG(net_pnl_usdt), 0) AS avg_net_pnl,
  COALESCE(SUM(gross_pnl_usdt), 0) AS total_gross_pnl,
  COALESCE(SUM(COALESCE(entry_fee, 0) + COALESCE(exit_fee, 0)), 0) AS total_fees,
  ROUND(
    (COUNT(*) FILTER (WHERE net_pnl_usdt > 0)::numeric / NULLIF(COUNT(*), 0) * 100)::numeric,
    2
  ) AS win_rate,
  ROUND(
    (COALESCE(SUM(net_pnl_usdt) FILTER (WHERE net_pnl_usdt > 0), 0) /
     NULLIF(ABS(COALESCE(SUM(net_pnl_usdt) FILTER (WHERE net_pnl_usdt < 0), 0)), 0))::numeric,
    4
  ) AS profit_factor,
  COALESCE(AVG(net_pnl_usdt) FILTER (WHERE net_pnl_usdt > 0), 0) AS avg_win,
  COALESCE(AVG(net_pnl_usdt) FILTER (WHERE net_pnl_usdt < 0), 0) AS avg_loss
FROM public.trades
WHERE closed_at IS NOT NULL
  AND net_pnl_usdt IS NOT NULL
GROUP BY strategy_family, strategy_name;

-- B) Vista: analytics_by_leverage
CREATE OR REPLACE VIEW public.analytics_by_leverage AS
SELECT
  leverage,
  COUNT(*)::int AS total_trades,
  COALESCE(SUM(net_pnl_usdt), 0) AS total_net_pnl,
  COALESCE(AVG(net_pnl_usdt), 0) AS avg_net_pnl,
  COALESCE(SUM(COALESCE(entry_fee, 0) + COALESCE(exit_fee, 0)), 0) AS total_fees,
  ROUND(
    (COUNT(*) FILTER (WHERE net_pnl_usdt > 0)::numeric / NULLIF(COUNT(*), 0) * 100)::numeric,
    2
  ) AS win_rate
FROM public.trades
WHERE closed_at IS NOT NULL
  AND net_pnl_usdt IS NOT NULL
GROUP BY leverage;

-- C) Vista: analytics_equity_curve (closed_at + PnL acumulado por trade, orden en consulta)
CREATE OR REPLACE VIEW public.analytics_equity_curve AS
SELECT
  id,
  closed_at,
  SUM(net_pnl_usdt) OVER (ORDER BY closed_at NULLS LAST, id) AS cumulative_net_pnl
FROM public.trades
WHERE closed_at IS NOT NULL
  AND net_pnl_usdt IS NOT NULL;

-- D) Vista: analytics_summary (una fila)
CREATE OR REPLACE VIEW public.analytics_summary AS
SELECT
  COUNT(*)::int AS total_closed_trades,
  COALESCE(SUM(net_pnl_usdt), 0) AS total_net_pnl,
  COALESCE(SUM(COALESCE(entry_fee, 0) + COALESCE(exit_fee, 0) + COALESCE(funding_fee, 0)), 0) AS total_fees,
  ROUND(
    (COUNT(*) FILTER (WHERE net_pnl_usdt > 0)::numeric / NULLIF(COUNT(*), 0) * 100)::numeric,
    2
  ) AS win_rate,
  (SELECT strategy_name FROM public.trades
   WHERE closed_at IS NOT NULL AND net_pnl_usdt IS NOT NULL
   GROUP BY strategy_name
   ORDER BY SUM(net_pnl_usdt) DESC
   LIMIT 1) AS best_strategy,
  (SELECT leverage FROM public.trades
   WHERE closed_at IS NOT NULL AND net_pnl_usdt IS NOT NULL
   GROUP BY leverage
   ORDER BY SUM(net_pnl_usdt) DESC
   LIMIT 1) AS best_leverage
FROM public.trades
WHERE closed_at IS NOT NULL
  AND net_pnl_usdt IS NOT NULL;

-- RLS: permitir lectura a los mismos roles que trades
ALTER VIEW public.analytics_by_strategy SET (security_invoker = false);
ALTER VIEW public.analytics_by_leverage SET (security_invoker = false);
ALTER VIEW public.analytics_equity_curve SET (security_invoker = false);
ALTER VIEW public.analytics_summary SET (security_invoker = false);

-- Función RPC: devuelve todo en un JSON para el frontend
CREATE OR REPLACE FUNCTION public.get_analytics()
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  by_strat json;
  by_lev json;
  curve json;
  summ json;
BEGIN
  SELECT COALESCE(json_agg(row_to_json(t)), '[]'::json)
  INTO by_strat
  FROM (
    SELECT strategy_family, strategy_name, total_trades, total_net_pnl, avg_net_pnl,
           total_gross_pnl, total_fees, win_rate, profit_factor, avg_win, avg_loss
    FROM public.analytics_by_strategy
  ) t;

  SELECT COALESCE(json_agg(row_to_json(t)), '[]'::json)
  INTO by_lev
  FROM (
    SELECT leverage, total_trades, total_net_pnl, avg_net_pnl, total_fees, win_rate
    FROM public.analytics_by_leverage
    ORDER BY leverage
  ) t;

  SELECT COALESCE(json_agg(row_to_json(t) ORDER BY t.closed_at NULLS LAST, t.id), '[]'::json)
  INTO curve
  FROM (
    SELECT id, closed_at, cumulative_net_pnl
    FROM public.analytics_equity_curve
    ORDER BY closed_at NULLS LAST, id
  ) t;

  SELECT row_to_json(s)
  INTO summ
  FROM public.analytics_summary s
  LIMIT 1;

  RETURN json_build_object(
    'by_strategy', COALESCE(by_strat, '[]'::json),
    'by_leverage', COALESCE(by_lev, '[]'::json),
    'equity_curve', COALESCE(curve, '[]'::json),
    'summary', COALESCE(summ, '{}'::json)
  );
END;
$$;

-- Permiso de ejecución
GRANT EXECUTE ON FUNCTION public.get_analytics() TO anon;
GRANT EXECUTE ON FUNCTION public.get_analytics() TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_analytics() TO service_role;

-- ============================================================
-- Backtest analytics (backtest_runs completados)
-- ============================================================

CREATE OR REPLACE VIEW public.analytics_backtest_summary AS
SELECT
  id AS run_id,
  strategy_name,
  symbol,
  interval,
  initial_capital,
  final_capital,
  COALESCE(net_pnl, 0) AS net_pnl,
  COALESCE(total_trades, 0)::int AS total_trades,
  win_rate,
  profit_factor,
  max_drawdown_pct AS drawdown_pct,
  CASE
    WHEN initial_capital IS NOT NULL AND initial_capital > 0 AND final_capital IS NOT NULL
    THEN ROUND(((final_capital - initial_capital) / initial_capital * 100)::numeric, 2)
    ELSE NULL
  END AS return_pct
FROM public.backtest_runs
WHERE status = 'completed'
  AND final_capital IS NOT NULL;
