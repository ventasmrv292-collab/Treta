-- ============================================================
-- Reparación manual de la tabla candles (elimina filas inválidas)
-- Ejecutar en Supabase SQL Editor. ELIMINA filas que incumplen reglas.
-- Hacer backup o ejecutar diagnose_candles.sql antes para ver cuántas se borrarán.
-- ============================================================

-- Rellenar close_time donde falte (para no borrar por NULL después)
UPDATE public.candles
SET close_time = open_time + (
  (CASE interval WHEN '1m' THEN 60 WHEN '5m' THEN 300 WHEN '15m' THEN 900 WHEN '1h' THEN 3600 ELSE 60 END)::text || ' seconds'
)::interval
WHERE close_time IS NULL;

-- Eliminar filas inválidas (en orden para no fallar por FK si en el futuro hubiera)
DELETE FROM public.candles WHERE volume < 0;

DELETE FROM public.candles
WHERE open <= 0 OR high <= 0 OR low <= 0 OR close <= 0;

DELETE FROM public.candles
WHERE high < GREATEST(open, close, low) OR low > LEAST(open, close, high);

DELETE FROM public.candles
WHERE close_time IS NOT NULL AND open_time >= close_time;

-- Duración incoherente con el intervalo (tolerancia 2 s)
DELETE FROM public.candles c
WHERE c.close_time IS NOT NULL
  AND ABS(EXTRACT(EPOCH FROM (c.close_time - c.open_time)) -
    (CASE c.interval WHEN '1m' THEN 60 WHEN '5m' THEN 300 WHEN '15m' THEN 900 WHEN '1h' THEN 3600 ELSE 60 END)::numeric) > 2;

DELETE FROM public.candles
WHERE interval IS NULL OR interval NOT IN ('1m','5m','15m','1h');

DELETE FROM public.candles
WHERE source IS NULL OR source NOT IN ('BINANCE','COINGECKO','MANUAL','IMPORT');

-- Duplicados: conservar la fila con id menor por (symbol, interval, open_time)
DELETE FROM public.candles c
USING public.candles c2
WHERE c.symbol = c2.symbol AND c.interval = c2.interval AND c.open_time = c2.open_time
  AND c.id > c2.id;
