-- ============================================================
-- Crypto Futures Sim - Esquema completo para Supabase (PostgreSQL)
-- Ejecutar en el SQL Editor de tu proyecto Supabase
-- ============================================================

-- Extensión para UUID si la necesitas más adelante (opcional)
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ------------------------------------------------------------
-- 1. STRATEGIES
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS strategies (
    id              SERIAL PRIMARY KEY,
    family          VARCHAR(64) NOT NULL,
    name            VARCHAR(128) NOT NULL,
    version         VARCHAR(32) NOT NULL,
    description     TEXT,
    default_params_json TEXT,
    active          BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_strategies_family ON strategies (family);

-- ------------------------------------------------------------
-- 2. FEE_CONFIGS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fee_configs (
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(64) NOT NULL UNIQUE,
    maker_fee_bps        NUMERIC(10, 4) NOT NULL,
    taker_fee_bps        NUMERIC(10, 4) NOT NULL,
    bnb_discount_pct     NUMERIC(5, 2) NOT NULL DEFAULT 0,
    default_slippage_bps NUMERIC(10, 2) NOT NULL DEFAULT 0,
    include_funding      BOOLEAN NOT NULL DEFAULT true,
    is_default          BOOLEAN NOT NULL DEFAULT false,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- 3. TRADES
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trades (
    id                  SERIAL PRIMARY KEY,
    source              VARCHAR(32) NOT NULL,
    symbol              VARCHAR(32) NOT NULL,
    market              VARCHAR(32) NOT NULL,
    strategy_family      VARCHAR(64) NOT NULL,
    strategy_name        VARCHAR(128) NOT NULL,
    strategy_version     VARCHAR(32) NOT NULL,
    strategy_id          INTEGER REFERENCES strategies(id),
    timeframe           VARCHAR(16) NOT NULL,
    position_side        VARCHAR(8) NOT NULL,
    order_side_entry     VARCHAR(8) NOT NULL,
    order_type_entry     VARCHAR(16) NOT NULL,
    maker_taker_entry    VARCHAR(8),
    leverage            INTEGER NOT NULL,
    quantity            NUMERIC(20, 8) NOT NULL,
    entry_price         NUMERIC(20, 8) NOT NULL,
    take_profit         NUMERIC(20, 8),
    stop_loss           NUMERIC(20, 8),
    signal_timestamp    TIMESTAMPTZ,
    strategy_params_json TEXT,
    notes               TEXT,
    exit_price          NUMERIC(20, 8),
    exit_order_type     VARCHAR(16),
    maker_taker_exit    VARCHAR(8),
    exit_reason         VARCHAR(64),
    closed_at           TIMESTAMPTZ,
    entry_notional      NUMERIC(20, 4),
    exit_notional       NUMERIC(20, 4),
    entry_fee           NUMERIC(20, 4),
    exit_fee            NUMERIC(20, 4),
    funding_fee         NUMERIC(20, 4),
    slippage_usdt       NUMERIC(20, 4),
    gross_pnl_usdt      NUMERIC(20, 4),
    net_pnl_usdt        NUMERIC(20, 4),
    pnl_pct_notional    NUMERIC(12, 4),
    pnl_pct_margin      NUMERIC(12, 4),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_trades_source ON trades (source);
CREATE INDEX IF NOT EXISTS ix_trades_symbol ON trades (symbol);
CREATE INDEX IF NOT EXISTS ix_trades_strategy_family ON trades (strategy_family);
CREATE INDEX IF NOT EXISTS ix_trades_strategy_id ON trades (strategy_id);
CREATE INDEX IF NOT EXISTS ix_trades_closed_at ON trades (closed_at);
CREATE INDEX IF NOT EXISTS ix_trades_created_at ON trades (created_at);

-- ------------------------------------------------------------
-- 4. CANDLES
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS candles (
    id          SERIAL PRIMARY KEY,
    symbol      VARCHAR(32) NOT NULL,
    interval    VARCHAR(8) NOT NULL,
    open_time   TIMESTAMPTZ NOT NULL,
    open        NUMERIC(20, 8) NOT NULL,
    high        NUMERIC(20, 8) NOT NULL,
    low         NUMERIC(20, 8) NOT NULL,
    close       NUMERIC(20, 8) NOT NULL,
    volume      NUMERIC(20, 4) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_candles_symbol_interval_time UNIQUE (symbol, interval, open_time)
);

CREATE INDEX IF NOT EXISTS ix_candles_symbol ON candles (symbol);
CREATE INDEX IF NOT EXISTS ix_candles_interval ON candles (interval);

-- ------------------------------------------------------------
-- 5. BACKTEST_RUNS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS backtest_runs (
    id                  SERIAL PRIMARY KEY,
    strategy_family      VARCHAR(64) NOT NULL,
    strategy_name        VARCHAR(128) NOT NULL,
    strategy_version     VARCHAR(32) NOT NULL,
    symbol              VARCHAR(32) NOT NULL,
    interval            VARCHAR(8) NOT NULL,
    start_time          TIMESTAMPTZ NOT NULL,
    end_time            TIMESTAMPTZ NOT NULL,
    initial_capital     NUMERIC(20, 4) NOT NULL,
    leverage            INTEGER NOT NULL,
    fee_profile         VARCHAR(32) NOT NULL,
    slippage_bps        NUMERIC(10, 2) NOT NULL,
    params_json         TEXT,
    status              VARCHAR(16) NOT NULL DEFAULT 'pending',
    total_trades        INTEGER,
    net_pnl             NUMERIC(20, 4),
    gross_pnl           NUMERIC(20, 4),
    total_fees          NUMERIC(20, 4),
    win_rate            NUMERIC(8, 4),
    profit_factor       NUMERIC(12, 4),
    max_drawdown_pct    NUMERIC(8, 4),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- 6. BACKTEST_RESULTS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS backtest_results (
    id              SERIAL PRIMARY KEY,
    run_id          INTEGER NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    trade_index      INTEGER NOT NULL,
    entry_time       TIMESTAMPTZ NOT NULL,
    exit_time        TIMESTAMPTZ NOT NULL,
    position_side     VARCHAR(8) NOT NULL,
    entry_price      NUMERIC(20, 8) NOT NULL,
    exit_price       NUMERIC(20, 8) NOT NULL,
    quantity         NUMERIC(20, 8) NOT NULL,
    gross_pnl        NUMERIC(20, 4) NOT NULL,
    fees             NUMERIC(20, 4) NOT NULL,
    net_pnl          NUMERIC(20, 4) NOT NULL,
    exit_reason      VARCHAR(64) NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_backtest_results_run_id ON backtest_results (run_id);

-- ------------------------------------------------------------
-- Trigger: actualizar updated_at en strategies y fee_configs
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_strategies_updated_at ON strategies;
CREATE TRIGGER trg_strategies_updated_at
    BEFORE UPDATE ON strategies
    FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

DROP TRIGGER IF EXISTS trg_fee_configs_updated_at ON fee_configs;
CREATE TRIGGER trg_fee_configs_updated_at
    BEFORE UPDATE ON fee_configs
    FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

DROP TRIGGER IF EXISTS trg_trades_updated_at ON trades;
CREATE TRIGGER trg_trades_updated_at
    BEFORE UPDATE ON trades
    FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

-- ============================================================
-- FIN DEL ESQUEMA
-- ============================================================
