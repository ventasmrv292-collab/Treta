-- ============================================================
-- Diagnóstico de calidad de la tabla candles
-- Ejecutar en Supabase SQL Editor. No modifica datos.
-- ============================================================

-- 1) Total por símbolo e intervalo
SELECT symbol, interval, COUNT(*) AS total
FROM public.candles
GROUP BY symbol, interval
ORDER BY symbol, interval;

-- 2) Filas con volume = 0
SELECT COUNT(*) AS zero_volume_count FROM public.candles WHERE volume = 0;

-- 3) Filas con volume < 0
SELECT COUNT(*) AS negative_volume_count FROM public.candles WHERE volume < 0;

-- 4) OHLC inválido (precios <= 0 o high/low incoherente)
SELECT COUNT(*) AS invalid_ohlc_count
FROM public.candles c
WHERE c.open <= 0 OR c.high <= 0 OR c.low <= 0 OR c.close <= 0
   OR c.high < GREATEST(c.open, c.close, c.low)
   OR c.low > LEAST(c.open, c.close, c.high);

-- 5) open_time >= close_time (cuando close_time existe)
SELECT COUNT(*) AS open_after_close_count
FROM public.candles
WHERE close_time IS NOT NULL AND open_time >= close_time;

-- 6) Interval no permitido
SELECT interval, COUNT(*) AS cnt
FROM public.candles
WHERE interval IS NULL OR interval NOT IN ('1m','5m','15m','1h')
GROUP BY interval;

-- 7) Duplicados por (symbol, interval, open_time)
WITH dup AS (
  SELECT symbol, interval, open_time, COUNT(*) AS cnt
  FROM public.candles
  GROUP BY symbol, interval, open_time
  HAVING COUNT(*) > 1
)
SELECT COUNT(*) AS duplicate_groups, COALESCE(SUM(cnt - 1), 0) AS extra_rows FROM dup;

-- 8) Filas donde close_time - open_time no coincide con el intervalo (tolerancia 2 s)
SELECT COUNT(*) AS interval_mismatch_count
FROM public.candles c
WHERE c.close_time IS NOT NULL
  AND ABS(EXTRACT(EPOCH FROM (c.close_time - c.open_time)) - 
    CASE c.interval
      WHEN '1m' THEN 60 WHEN '5m' THEN 300 WHEN '15m' THEN 900 WHEN '1h' THEN 3600
      ELSE 60 END::numeric) > 2;

-- 9) Resumen rápido
SELECT
  (SELECT COUNT(*) FROM public.candles) AS total_rows,
  (SELECT COUNT(*) FROM public.candles WHERE volume = 0) AS zero_volume,
  (SELECT COUNT(*) FROM public.candles WHERE volume < 0) AS negative_volume,
  (SELECT COUNT(*) FROM public.candles WHERE close_time IS NULL) AS null_close_time;
