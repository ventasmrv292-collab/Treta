-- ============================================================
-- Función RPC: control de calidad de la tabla candles
-- Devuelve conteos de filas revisadas, inválidas, duplicados, huecos, volumen cero, intervalo incoherente.
-- ============================================================

CREATE OR REPLACE FUNCTION public.get_candles_quality_report(
  p_symbol   TEXT DEFAULT NULL,
  p_interval TEXT DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
  total_rows        BIGINT;
  invalid_volume    BIGINT;
  invalid_ohlc      BIGINT;
  invalid_interval  BIGINT;
  open_after_close  BIGINT;
  duplicates        BIGINT;
  zero_volume       BIGINT;
  interval_mismatch BIGINT;
  temporal_gaps    BIGINT;
  filter_sym        TEXT := NULLIF(TRIM(p_symbol), '');
  filter_int        TEXT := NULLIF(TRIM(p_interval), '');
BEGIN
  -- Total filas (opcionalmente filtradas)
  SELECT COUNT(*) INTO total_rows
  FROM public.candles c
  WHERE (filter_sym IS NULL OR c.symbol = filter_sym)
    AND (filter_int IS NULL OR c.interval = filter_int);

  -- Volume < 0
  SELECT COUNT(*) INTO invalid_volume
  FROM public.candles c
  WHERE c.volume < 0
    AND (filter_sym IS NULL OR c.symbol = filter_sym)
    AND (filter_int IS NULL OR c.interval = filter_int);

  -- OHLC inválido (precios <= 0 o high/low incoherente)
  SELECT COUNT(*) INTO invalid_ohlc
  FROM public.candles c
  WHERE (c.open <= 0 OR c.high <= 0 OR c.low <= 0 OR c.close <= 0
         OR c.high < GREATEST(c.open, c.close, c.low)
         OR c.low > LEAST(c.open, c.close, c.high))
    AND (filter_sym IS NULL OR c.symbol = filter_sym)
    AND (filter_int IS NULL OR c.interval = filter_int);

  -- open_time >= close_time
  SELECT COUNT(*) INTO open_after_close
  FROM public.candles c
  WHERE c.close_time IS NOT NULL AND c.open_time >= c.close_time
    AND (filter_sym IS NULL OR c.symbol = filter_sym)
    AND (filter_int IS NULL OR c.interval = filter_int);

  -- Interval no permitido
  SELECT COUNT(*) INTO invalid_interval
  FROM public.candles c
  WHERE c.interval IS NULL OR c.interval NOT IN ('1m','5m','15m','1h')
    AND (filter_sym IS NULL OR c.symbol = filter_sym)
    AND (filter_int IS NULL OR c.interval = filter_int);

  -- Volumen cero
  SELECT COUNT(*) INTO zero_volume
  FROM public.candles c
  WHERE c.volume = 0
    AND (filter_sym IS NULL OR c.symbol = filter_sym)
    AND (filter_int IS NULL OR c.interval = filter_int);

  -- Duración close_time - open_time no coincide con intervalo (tolerancia 2s)
  SELECT COUNT(*) INTO interval_mismatch
  FROM public.candles c
  WHERE c.close_time IS NOT NULL
    AND ABS(EXTRACT(EPOCH FROM (c.close_time - c.open_time)) - public.candles_interval_duration_seconds(c.interval)::numeric) > 2
    AND (filter_sym IS NULL OR c.symbol = filter_sym)
    AND (filter_int IS NULL OR c.interval = filter_int);

  -- Duplicados por (symbol, interval, open_time)
  WITH dup AS (
    SELECT c.symbol, c.interval, c.open_time, COUNT(*) AS cnt
    FROM public.candles c
    WHERE (filter_sym IS NULL OR c.symbol = filter_sym)
      AND (filter_int IS NULL OR c.interval = filter_int)
    GROUP BY c.symbol, c.interval, c.open_time
    HAVING COUNT(*) > 1
  )
  SELECT COALESCE(SUM(cnt - 1), 0)::BIGINT INTO duplicates FROM dup;

  -- Huecos temporales: para cada (symbol, interval) contar gaps donde la siguiente vela no es open_time + interval
  WITH ordered AS (
    SELECT c.symbol, c.interval, c.open_time,
           LEAD(c.open_time) OVER (PARTITION BY c.symbol, c.interval ORDER BY c.open_time) AS next_open
    FROM public.candles c
    WHERE (filter_sym IS NULL OR c.symbol = filter_sym)
      AND (filter_int IS NULL OR c.interval = filter_int)
  ),
  expected_next AS (
    SELECT symbol, interval, open_time, next_open,
           open_time + (public.candles_interval_duration_seconds(interval)::text || ' seconds')::interval AS expected
    FROM ordered
    WHERE next_open IS NOT NULL
  )
  SELECT COUNT(*)::BIGINT INTO temporal_gaps
  FROM expected_next
  WHERE next_open != expected;

  RETURN jsonb_build_object(
    'total_rows', total_rows,
    'invalid_volume', invalid_volume,
    'invalid_ohlc', invalid_ohlc,
    'open_after_close', open_after_close,
    'invalid_interval', invalid_interval,
    'zero_volume', zero_volume,
    'interval_mismatch', interval_mismatch,
    'duplicates', duplicates,
    'temporal_gaps', temporal_gaps,
    'filter_symbol', COALESCE(filter_sym, ''),
    'filter_interval', COALESCE(filter_int, '')
  );
END;
$$;

COMMENT ON FUNCTION public.get_candles_quality_report IS 'Reporte de calidad de candles: total, inválidos, duplicados, huecos, volumen cero, intervalo incoherente. Opcional: p_symbol, p_interval.';
