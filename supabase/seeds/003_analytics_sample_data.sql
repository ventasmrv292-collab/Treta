-- ============================================================
-- Seed OPCIONAL: datos de ejemplo para probar la pantalla Analíticas
-- Ejecutar solo si quieres ver la pantalla con datos sin tener trades reales.
-- Requiere: 001_initial_seed.sql (strategies, fee_configs, paper_accounts)
-- ============================================================

-- Solo insertar si no hay trades cerrados
DO $$
DECLARE
  closed_count int;
  acc_id bigint;
  fee_id int;
  sid_break int;
  sid_mean int;
  sid_trend int;
BEGIN
  SELECT COUNT(*) INTO closed_count FROM public.trades WHERE closed_at IS NOT NULL AND net_pnl_usdt IS NOT NULL;
  IF closed_count > 0 THEN
    RAISE NOTICE 'Ya existen trades cerrados, omitiendo seed de ejemplo.';
    RETURN;
  END IF;

  SELECT id INTO acc_id FROM public.paper_accounts LIMIT 1;
  SELECT id INTO fee_id FROM public.fee_configs WHERE is_default = true LIMIT 1;
  SELECT id INTO sid_break FROM public.strategies WHERE family = 'BREAKOUT' LIMIT 1;
  SELECT id INTO sid_mean FROM public.strategies WHERE family = 'MEAN_REVERSION' LIMIT 1;
  SELECT id INTO sid_trend FROM public.strategies WHERE family = 'TREND_PULLBACK' LIMIT 1;

  IF acc_id IS NULL OR fee_id IS NULL THEN
    RAISE NOTICE 'Ejecuta primero 001_initial_seed.sql.';
    RETURN;
  END IF;

  INSERT INTO public.trades (
    source, symbol, market, strategy_family, strategy_name, strategy_version,
    timeframe, position_side, order_side_entry, order_type_entry, leverage,
    quantity, entry_price, exit_price, closed_at, status,
    entry_notional, exit_notional, entry_fee, exit_fee, gross_pnl_usdt, net_pnl_usdt,
    account_id, fee_config_id, strategy_id, opened_at
  ) VALUES
    ('MANUAL', 'BTCUSDT', 'PERP', 'BREAKOUT', 'breakout_volume_v1', '1.0.0', '15m', 'LONG', 'BUY', 'MARKET', 10,
     0.001, 95000, 96200, '2025-03-01 10:00:00+00', 'CLOSED',
     95.00, 96.20, 0.38, 0.38, 1.20, 0.44, acc_id, fee_id, sid_break, '2025-03-01 09:30:00+00'),
    ('MANUAL', 'BTCUSDT', 'PERP', 'BREAKOUT', 'breakout_volume_v1', '1.0.0', '15m', 'LONG', 'BUY', 'MARKET', 10,
     0.001, 96000, 95800, '2025-03-02 14:00:00+00', 'CLOSED',
     96.00, 95.80, 0.38, 0.38, -0.20, -0.96, acc_id, fee_id, sid_break, '2025-03-02 13:00:00+00'),
    ('MANUAL', 'BTCUSDT', 'PERP', 'MEAN_REVERSION', 'vwap_snapback_v1', '1.0.0', '15m', 'LONG', 'BUY', 'MARKET', 20,
     0.0005, 94000, 94800, '2025-03-03 11:00:00+00', 'CLOSED',
     47.00, 47.40, 0.19, 0.19, 0.40, 0.02, acc_id, fee_id, sid_mean, '2025-03-03 10:00:00+00'),
    ('MANUAL', 'BTCUSDT', 'PERP', 'MEAN_REVERSION', 'vwap_snapback_v1', '1.0.0', '15m', 'SHORT', 'SELL', 'MARKET', 20,
     0.0005, 95200, 94600, '2025-03-04 16:00:00+00', 'CLOSED',
     47.60, 47.30, 0.19, 0.19, 0.30, -0.08, acc_id, fee_id, sid_mean, '2025-03-04 15:00:00+00'),
    ('MANUAL', 'BTCUSDT', 'PERP', 'TREND_PULLBACK', 'ema_pullback_v1', '1.0.0', '15m', 'LONG', 'BUY', 'MARKET', 10,
     0.002, 93500, 94200, '2025-03-05 09:00:00+00', 'CLOSED',
     187.00, 188.40, 0.75, 0.75, 1.40, -0.10, acc_id, fee_id, sid_trend, '2025-03-05 08:00:00+00'),
    ('MANUAL', 'BTCUSDT', 'PERP', 'TREND_PULLBACK', 'ema_pullback_v1', '1.0.0', '15m', 'LONG', 'BUY', 'MARKET', 20,
     0.001, 93800, 95200, '2025-03-06 12:00:00+00', 'CLOSED',
     93.80, 95.20, 0.38, 0.38, 1.40, 0.64, acc_id, fee_id, sid_trend, '2025-03-06 11:00:00+00');

  RAISE NOTICE 'Insertados 6 trades cerrados de ejemplo para Analíticas.';
END $$;

-- Backtest runs de ejemplo (solo si no hay runs completados)
DO $$
DECLARE
  run_count int;
  run_id int;
  strat_id int;
BEGIN
  SELECT COUNT(*) INTO run_count FROM public.backtest_runs WHERE status = 'completed';
  IF run_count > 0 THEN
    RAISE NOTICE 'Ya existen backtest runs completados, omitiendo.';
    RETURN;
  END IF;

  SELECT id INTO strat_id FROM public.strategies WHERE family = 'BREAKOUT' LIMIT 1;
  IF strat_id IS NULL THEN RETURN; END IF;

  INSERT INTO public.backtest_runs (
    strategy_family, strategy_name, strategy_version, strategy_id, symbol, interval,
    start_time, end_time, initial_capital, leverage, fee_profile, slippage_bps,
    status, total_trades, net_pnl, gross_pnl, total_fees, win_rate, profit_factor,
    max_drawdown_pct, final_capital, peak_equity, min_equity
  ) VALUES
  (
    'BREAKOUT', 'breakout_volume_v1', '1.0.0', strat_id, 'BTCUSDT', '15m',
    '2025-02-01 00:00:00+00', '2025-02-28 23:59:00+00', 1000, 10, 'default', 5,
    'completed', 12, 45.50, 48.00, 2.50, 58.33, 1.45,
    5.2, 1045.50, 1052.00, 998.00
  )
  RETURNING id INTO run_id;

  INSERT INTO public.backtest_equity_curve (run_id, point_time, equity_usdt, balance_usdt, used_margin_usdt, drawdown_pct)
  VALUES
    (run_id, '2025-02-05 12:00:00+00', 1008.00, 1000.00, 8.00, 0),
    (run_id, '2025-02-10 12:00:00+00', 1015.00, 1000.00, 15.00, 0),
    (run_id, '2025-02-15 12:00:00+00', 1002.00, 987.00, 15.00, 1.3),
    (run_id, '2025-02-20 12:00:00+00', 1035.00, 1020.00, 15.00, 0),
    (run_id, '2025-02-28 23:59:00+00', 1045.50, 1045.50, 0, 0);

  RAISE NOTICE 'Insertado 1 backtest run de ejemplo con curva de equity.';
END $$;
