-- ============================================================
-- Migración 03: ALTER backtest_runs, candles, strategies, fee_configs
-- ============================================================

ALTER TABLE public.backtest_runs
    ADD COLUMN IF NOT EXISTS strategy_id INTEGER NULL REFERENCES public.strategies(id),
    ADD COLUMN IF NOT EXISTS fee_config_id INTEGER NULL REFERENCES public.fee_configs(id),
    ADD COLUMN IF NOT EXISTS final_capital NUMERIC(20, 4) NULL,
    ADD COLUMN IF NOT EXISTS peak_equity NUMERIC(20, 4) NULL,
    ADD COLUMN IF NOT EXISTS min_equity NUMERIC(20, 4) NULL,
    ADD COLUMN IF NOT EXISTS total_funding NUMERIC(20, 4) NULL,
    ADD COLUMN IF NOT EXISTS total_slippage NUMERIC(20, 4) NULL,
    ADD COLUMN IF NOT EXISTS used_margin_peak NUMERIC(20, 4) NULL;

ALTER TABLE public.candles
    ADD COLUMN IF NOT EXISTS close_time TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS is_closed BOOLEAN NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS source VARCHAR(32) NOT NULL DEFAULT 'BINANCE';

CREATE INDEX IF NOT EXISTS ix_candles_symbol_interval_open_time
    ON public.candles (symbol, interval, open_time DESC);

ALTER TABLE public.strategies
    DROP CONSTRAINT IF EXISTS uq_strategies_family_name_version;
ALTER TABLE public.strategies
    ADD CONSTRAINT uq_strategies_family_name_version UNIQUE (family, name, version);

CREATE UNIQUE INDEX IF NOT EXISTS ux_fee_configs_single_default
    ON public.fee_configs (is_default) WHERE is_default = true;
