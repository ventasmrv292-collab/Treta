-- ============================================================
-- Candles: esquema robusto, validaciones e integridad temporal
-- Elimina filas inválidas antes de añadir CHECKs.
-- ============================================================

-- 1) Función auxiliar: duración esperada del intervalo en segundos (se usa en limpieza y en trigger)
CREATE OR REPLACE FUNCTION public.candles_interval_duration_seconds(i TEXT)
RETURNS INT
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT CASE i
    WHEN '1m'  THEN 60
    WHEN '5m'  THEN 300
    WHEN '15m' THEN 900
    WHEN '1h'  THEN 3600
    ELSE 60
  END;
$$;

-- 2) Columnas nuevas (si no existen)
ALTER TABLE public.candles
  ADD COLUMN IF NOT EXISTS quote_volume          NUMERIC(20, 4) NULL,
  ADD COLUMN IF NOT EXISTS trade_count           INTEGER NULL,
  ADD COLUMN IF NOT EXISTS taker_buy_base_volume  NUMERIC(20, 4) NULL,
  ADD COLUMN IF NOT EXISTS taker_buy_quote_volume NUMERIC(20, 4) NULL,
  ADD COLUMN IF NOT EXISTS ingested_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS validation_status     VARCHAR(16) NOT NULL DEFAULT 'PENDING',
  ADD COLUMN IF NOT EXISTS validation_notes      TEXT NULL;

-- 3) Rellenar close_time donde falte (para filas antiguas)
UPDATE public.candles
SET close_time = open_time + (public.candles_interval_duration_seconds(interval)::text || ' seconds')::interval
WHERE close_time IS NULL;

-- 4) Eliminar filas que incumplen reglas de integridad (para poder añadir CHECKs)
DELETE FROM public.candles WHERE volume < 0;
DELETE FROM public.candles WHERE open <= 0 OR high <= 0 OR low <= 0 OR close <= 0;
DELETE FROM public.candles
WHERE high < GREATEST(open, close, low) OR low > LEAST(open, close, high);
DELETE FROM public.candles WHERE close_time IS NOT NULL AND open_time >= close_time;
DELETE FROM public.candles c
WHERE c.close_time IS NOT NULL
  AND ABS(EXTRACT(EPOCH FROM (c.close_time - c.open_time)) - public.candles_interval_duration_seconds(c.interval)::numeric) > 2;
DELETE FROM public.candles WHERE interval NOT IN ('1m','5m','15m','1h');
DELETE FROM public.candles WHERE source IS NULL OR source NOT IN ('BINANCE','COINGECKO','MANUAL','IMPORT');

-- 5) Constraints
ALTER TABLE public.candles DROP CONSTRAINT IF EXISTS chk_candles_interval;
ALTER TABLE public.candles ADD CONSTRAINT chk_candles_interval CHECK (interval IN ('1m','5m','15m','1h'));

ALTER TABLE public.candles DROP CONSTRAINT IF EXISTS chk_candles_source;
ALTER TABLE public.candles ADD CONSTRAINT chk_candles_source CHECK (source IN ('BINANCE','COINGECKO','MANUAL','IMPORT'));

ALTER TABLE public.candles DROP CONSTRAINT IF EXISTS chk_candles_volume;
ALTER TABLE public.candles ADD CONSTRAINT chk_candles_volume CHECK (volume >= 0);

ALTER TABLE public.candles DROP CONSTRAINT IF EXISTS chk_candles_ohlc_positive;
ALTER TABLE public.candles ADD CONSTRAINT chk_candles_ohlc_positive CHECK (open > 0 AND high > 0 AND low > 0 AND close > 0);

ALTER TABLE public.candles DROP CONSTRAINT IF EXISTS chk_candles_high_low;
ALTER TABLE public.candles ADD CONSTRAINT chk_candles_high_low
  CHECK (high >= GREATEST(open, close, low) AND low <= LEAST(open, close, high));

ALTER TABLE public.candles DROP CONSTRAINT IF EXISTS chk_candles_open_before_close;
ALTER TABLE public.candles ADD CONSTRAINT chk_candles_open_before_close CHECK (close_time IS NULL OR open_time < close_time);

ALTER TABLE public.candles DROP CONSTRAINT IF EXISTS chk_candles_validation_status;
ALTER TABLE public.candles ADD CONSTRAINT chk_candles_validation_status
  CHECK (validation_status IN ('PENDING','VALID','INVALID'));

-- 6) Trigger: validar duración temporal antes de INSERT/UPDATE
CREATE OR REPLACE FUNCTION public.candles_validate_interval_duration()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
  expected_sec INT;
  actual_sec   NUMERIC;
  tolerance   NUMERIC := 2;
BEGIN
  IF NEW.close_time IS NULL THEN
    RETURN NEW;
  END IF;
  expected_sec := public.candles_interval_duration_seconds(NEW.interval);
  actual_sec   := EXTRACT(EPOCH FROM (NEW.close_time - NEW.open_time));
  IF actual_sec < (expected_sec - tolerance) OR actual_sec > (expected_sec + tolerance) THEN
    RAISE EXCEPTION 'candles: interval duration mismatch. interval=%, open_time=%, close_time=%, expected_sec=%, actual_sec=%',
      NEW.interval, NEW.open_time, NEW.close_time, expected_sec, actual_sec;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_candles_validate_interval ON public.candles;
CREATE TRIGGER trg_candles_validate_interval
  BEFORE INSERT OR UPDATE OF open_time, close_time, interval
  ON public.candles
  FOR EACH ROW
  EXECUTE PROCEDURE public.candles_validate_interval_duration();

-- 7) Trigger updated_at
CREATE OR REPLACE FUNCTION public.candles_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_candles_updated_at ON public.candles;
CREATE TRIGGER trg_candles_updated_at
  BEFORE UPDATE ON public.candles
  FOR EACH ROW
  EXECUTE PROCEDURE public.candles_updated_at();

-- 12) Índices para backtesting y consultas por rango
CREATE INDEX IF NOT EXISTS ix_candles_symbol_interval_open_time_desc
  ON public.candles (symbol, interval, open_time DESC);

CREATE INDEX IF NOT EXISTS ix_candles_is_closed
  ON public.candles (symbol, interval, is_closed) WHERE is_closed = true;

CREATE INDEX IF NOT EXISTS ix_candles_ingested_at
  ON public.candles (ingested_at);

-- 13) Comentarios
COMMENT ON COLUMN public.candles.validation_status IS 'PENDING | VALID | INVALID';
COMMENT ON COLUMN public.candles.ingested_at IS 'Momento en que se insertó/actualizó la fila en nuestro sistema';
COMMENT ON COLUMN public.candles.close_time IS 'Timestamp de cierre de la vela (Binance: fin del intervalo)';
