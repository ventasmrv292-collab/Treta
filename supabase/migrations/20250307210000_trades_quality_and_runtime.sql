-- ============================================================
-- Trades: validaciones de calidad + tabla strategy_runtime_config
-- Ejecutar en Supabase SQL Editor (o via supabase db push).
-- ============================================================

-- 1) Corregir filas CLOSED con datos faltantes (para poder añadir CHECKs)
UPDATE public.trades
SET
  closed_at = COALESCE(closed_at, updated_at),
  exit_price = COALESCE(exit_price, entry_price),
  net_pnl_usdt = COALESCE(net_pnl_usdt, 0)
WHERE status = 'CLOSED' AND (closed_at IS NULL OR exit_price IS NULL OR net_pnl_usdt IS NULL);

UPDATE public.trades
SET status = 'CLOSED'
WHERE closed_at IS NOT NULL AND (status IS NULL OR status = 'OPEN');

-- 2) CHECK: consistencia status OPEN vs CLOSED
ALTER TABLE public.trades DROP CONSTRAINT IF EXISTS chk_trades_status_closed_fields;
ALTER TABLE public.trades ADD CONSTRAINT chk_trades_status_closed_fields CHECK (
  (status = 'OPEN' AND closed_at IS NULL AND exit_price IS NULL AND net_pnl_usdt IS NULL)
  OR
  (status = 'CLOSED' AND closed_at IS NOT NULL AND exit_price IS NOT NULL AND net_pnl_usdt IS NOT NULL)
);

-- 3) CHECK: source BACKEND => strategy_id obligatorio
ALTER TABLE public.trades DROP CONSTRAINT IF EXISTS chk_trades_backend_strategy;
ALTER TABLE public.trades ADD CONSTRAINT chk_trades_backend_strategy CHECK (
  source <> 'BACKEND' OR strategy_id IS NOT NULL
);

-- 4) (Índice único idempotency_key ya existe en migración 02)

-- 5) Trigger: asignar fee_config por defecto si viene NULL
CREATE OR REPLACE FUNCTION public.trades_set_default_fee_config()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE default_fee_id INT;
BEGIN
  SELECT id INTO default_fee_id FROM public.fee_configs WHERE is_default = true LIMIT 1;
  IF default_fee_id IS NOT NULL AND NEW.fee_config_id IS NULL THEN
    NEW.fee_config_id := default_fee_id;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_trades_set_default_fee_config ON public.trades;
CREATE TRIGGER trg_trades_set_default_fee_config
  BEFORE INSERT OR UPDATE OF fee_config_id ON public.trades
  FOR EACH ROW EXECUTE PROCEDURE public.trades_set_default_fee_config();

-- 6) Tabla strategy_runtime_config (control por estrategia / timeframe / dirección)
CREATE TABLE IF NOT EXISTS public.strategy_runtime_config (
  id                            SERIAL PRIMARY KEY,
  strategy_id                   INTEGER NOT NULL REFERENCES public.strategies(id) ON DELETE CASCADE,
  symbol                        VARCHAR(32) NOT NULL DEFAULT 'BTCUSDT',
  timeframe                     VARCHAR(16) NOT NULL,
  allow_long                    BOOLEAN NOT NULL DEFAULT true,
  allow_short                   BOOLEAN NOT NULL DEFAULT true,
  active                        BOOLEAN NOT NULL DEFAULT true,
  max_open_positions            INTEGER NOT NULL DEFAULT 1,
  cooldown_minutes              INTEGER NOT NULL DEFAULT 0,
  min_win_rate_threshold        NUMERIC(5,2),
  max_recent_drawdown_threshold NUMERIC(8,4),
  created_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_strategy_runtime_cfg
  ON public.strategy_runtime_config (strategy_id, symbol, timeframe);

CREATE OR REPLACE FUNCTION public.strategy_runtime_config_set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_strategy_runtime_config_updated_at ON public.strategy_runtime_config;
CREATE TRIGGER trg_strategy_runtime_config_updated_at
  BEFORE UPDATE ON public.strategy_runtime_config
  FOR EACH ROW EXECUTE PROCEDURE public.strategy_runtime_config_set_updated_at();
