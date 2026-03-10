-- ============================================================
-- Configuración inicial de strategy_runtime_config según diagnóstico:
-- - vwap_snapback: desactivar SHORT y desactivar 1m
-- - breakout_volume: priorizar, 15m activo
-- ============================================================

DO $$
DECLARE
  sid_break INT;
  sid_vwap  INT;
  sid_ema   INT;
BEGIN
  SELECT id INTO sid_break FROM public.strategies
  WHERE family = 'BREAKOUT' AND name = 'breakout_volume_v1' LIMIT 1;

  SELECT id INTO sid_vwap FROM public.strategies
  WHERE family = 'MEAN_REVERSION' AND name = 'vwap_snapback_v1' LIMIT 1;

  SELECT id INTO sid_ema FROM public.strategies
  WHERE family = 'TREND_PULLBACK' AND name = 'ema_pullback_v1' LIMIT 1;

  -- BREAKOUT: priorizar, solo LONG, 15m con hasta 2 posiciones
  IF sid_break IS NOT NULL THEN
    INSERT INTO public.strategy_runtime_config (strategy_id, symbol, timeframe, allow_long, allow_short, active, max_open_positions, cooldown_minutes)
    VALUES
      (sid_break, 'BTCUSDT', '1m',  true, false, true, 1, 0),
      (sid_break, 'BTCUSDT', '5m',  true, false, true, 1, 0),
      (sid_break, 'BTCUSDT', '15m', true, false, true, 2, 0)
    ON CONFLICT (strategy_id, symbol, timeframe) DO UPDATE SET
      allow_long = EXCLUDED.allow_long,
      allow_short = EXCLUDED.allow_short,
      active = EXCLUDED.active,
      max_open_positions = EXCLUDED.max_open_positions,
      cooldown_minutes = EXCLUDED.cooldown_minutes;
  END IF;

  -- VWAP: desactivar 1m; 5m y 15m solo LONG, cooldown 5 min
  IF sid_vwap IS NOT NULL THEN
    INSERT INTO public.strategy_runtime_config (strategy_id, symbol, timeframe, allow_long, allow_short, active, max_open_positions, cooldown_minutes)
    VALUES (sid_vwap, 'BTCUSDT', '1m', true, false, false, 0, 0)
    ON CONFLICT (strategy_id, symbol, timeframe) DO UPDATE SET
      allow_long = EXCLUDED.allow_long,
      allow_short = EXCLUDED.allow_short,
      active = EXCLUDED.active,
      max_open_positions = EXCLUDED.max_open_positions,
      cooldown_minutes = EXCLUDED.cooldown_minutes;

    INSERT INTO public.strategy_runtime_config (strategy_id, symbol, timeframe, allow_long, allow_short, active, max_open_positions, cooldown_minutes)
    VALUES
      (sid_vwap, 'BTCUSDT', '5m',  true, false, true, 1, 5),
      (sid_vwap, 'BTCUSDT', '15m', true, false, true, 1, 5)
    ON CONFLICT (strategy_id, symbol, timeframe) DO UPDATE SET
      allow_long = EXCLUDED.allow_long,
      allow_short = EXCLUDED.allow_short,
      active = EXCLUDED.active,
      max_open_positions = EXCLUDED.max_open_positions,
      cooldown_minutes = EXCLUDED.cooldown_minutes;
  END IF;

  -- EMA: activo en 5m y 15m
  IF sid_ema IS NOT NULL THEN
    INSERT INTO public.strategy_runtime_config (strategy_id, symbol, timeframe, allow_long, allow_short, active, max_open_positions, cooldown_minutes)
    VALUES
      (sid_ema, 'BTCUSDT', '5m',  true, true, true, 1, 0),
      (sid_ema, 'BTCUSDT', '15m', true, true, true, 1, 0)
    ON CONFLICT (strategy_id, symbol, timeframe) DO UPDATE SET
      allow_long = EXCLUDED.allow_long,
      allow_short = EXCLUDED.allow_short,
      active = EXCLUDED.active,
      max_open_positions = EXCLUDED.max_open_positions,
      cooldown_minutes = EXCLUDED.cooldown_minutes;
  END IF;
END $$;
