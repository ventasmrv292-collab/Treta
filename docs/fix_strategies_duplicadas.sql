-- ============================================================
-- Eliminar estrategias duplicadas (version 'v1') y quedarse con '1.0.0'
-- El backend solo usa (family, name, version) = (..., '1.0.0').
-- Ejecutar en Supabase SQL Editor.
-- ============================================================

-- 1) Reasignar trades que apunten a las estrategias v1 (id 1,2,3) hacia las 1.0.0 (id 4,5,6)
--    Suponiendo: id 1 (BREAKOUT v1) -> 4 (BREAKOUT 1.0.0), 2 -> 5, 3 -> 6
UPDATE public.trades
SET strategy_id = CASE strategy_id
  WHEN 1 THEN 4
  WHEN 2 THEN 5
  WHEN 3 THEN 6
  ELSE strategy_id
END
WHERE strategy_id IN (1, 2, 3);

-- 2) Opcional: reasignar backtest_runs si tienen strategy_id 1,2,3
UPDATE public.backtest_runs
SET strategy_id = CASE strategy_id
  WHEN 1 THEN 4
  WHEN 2 THEN 5
  WHEN 3 THEN 6
  ELSE strategy_id
END
WHERE strategy_id IN (1, 2, 3);

-- 3) Borrar las estrategias con version 'v1' (ids 1, 2, 3)
--    Verifica antes que los ids correctos son los de version 'v1' en tu tabla.
DELETE FROM public.strategies
WHERE (family, name, version) IN (
  ('BREAKOUT', 'breakout_volume_v1', 'v1'),
  ('MEAN_REVERSION', 'vwap_snapback_v1', 'v1'),
  ('TREND_PULLBACK', 'ema_pullback_v1', 'v1')
);

-- Comprobar resultado: solo deben quedar 3 filas con version '1.0.0'
-- SELECT id, family, name, version FROM public.strategies ORDER BY id;
