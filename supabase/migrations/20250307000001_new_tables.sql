-- ============================================================
-- Migración 01: paper_accounts, signal_events, backtest_equity_curve, account_ledger
-- ============================================================

-- A) paper_accounts
CREATE TABLE IF NOT EXISTS public.paper_accounts (
    id                      BIGSERIAL PRIMARY KEY,
    name                    VARCHAR(64) NOT NULL,
    base_currency            VARCHAR(16) NOT NULL DEFAULT 'USDT',
    initial_balance_usdt     NUMERIC(20, 4) NOT NULL,
    current_balance_usdt     NUMERIC(20, 4) NOT NULL,
    available_balance_usdt   NUMERIC(20, 4) NOT NULL,
    used_margin_usdt        NUMERIC(20, 4) NOT NULL DEFAULT 0,
    realized_pnl_usdt       NUMERIC(20, 4) NOT NULL DEFAULT 0,
    unrealized_pnl_usdt     NUMERIC(20, 4) NOT NULL DEFAULT 0,
    total_fees_usdt         NUMERIC(20, 4) NOT NULL DEFAULT 0,
    status                  VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
DROP TRIGGER IF EXISTS trg_paper_accounts_updated_at ON public.paper_accounts;
CREATE TRIGGER trg_paper_accounts_updated_at
    BEFORE UPDATE ON public.paper_accounts
    FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

-- B) signal_events
CREATE TABLE IF NOT EXISTS public.signal_events (
    id                BIGSERIAL PRIMARY KEY,
    source            VARCHAR(32) NOT NULL,
    external_id       VARCHAR(128) NULL,
    idempotency_key   VARCHAR(128) NULL,
    symbol            VARCHAR(32) NOT NULL,
    timeframe         VARCHAR(16) NOT NULL,
    strategy_family   VARCHAR(64) NOT NULL,
    strategy_name     VARCHAR(128) NOT NULL,
    strategy_version  VARCHAR(32) NOT NULL,
    payload_json      TEXT NOT NULL,
    status            VARCHAR(16) NOT NULL DEFAULT 'RECEIVED',
    decision_reason   TEXT NULL,
    trade_id          INTEGER NULL REFERENCES public.trades(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at      TIMESTAMPTZ NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_signal_events_idempotency
    ON public.signal_events (idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_signal_events_status ON public.signal_events (status);
CREATE INDEX IF NOT EXISTS ix_signal_events_created_at ON public.signal_events (created_at);

-- C) backtest_equity_curve
CREATE TABLE IF NOT EXISTS public.backtest_equity_curve (
    id                  BIGSERIAL PRIMARY KEY,
    run_id              INTEGER NOT NULL REFERENCES public.backtest_runs(id) ON DELETE CASCADE,
    point_time          TIMESTAMPTZ NOT NULL,
    equity_usdt         NUMERIC(20, 4) NOT NULL,
    balance_usdt        NUMERIC(20, 4) NOT NULL,
    used_margin_usdt    NUMERIC(20, 4) NOT NULL DEFAULT 0,
    drawdown_pct        NUMERIC(12, 4) NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_backtest_equity_curve_run_id ON public.backtest_equity_curve (run_id);
CREATE INDEX IF NOT EXISTS ix_backtest_equity_curve_point_time ON public.backtest_equity_curve (point_time);

-- D) account_ledger
CREATE TABLE IF NOT EXISTS public.account_ledger (
    id                   BIGSERIAL PRIMARY KEY,
    account_id           BIGINT NOT NULL REFERENCES public.paper_accounts(id) ON DELETE CASCADE,
    trade_id             INTEGER NULL REFERENCES public.trades(id) ON DELETE SET NULL,
    backtest_run_id      INTEGER NULL REFERENCES public.backtest_runs(id) ON DELETE SET NULL,
    event_type           VARCHAR(32) NOT NULL,
    amount_usdt          NUMERIC(20, 4) NOT NULL,
    balance_before_usdt  NUMERIC(20, 4) NOT NULL,
    balance_after_usdt   NUMERIC(20, 4) NOT NULL,
    meta_json            TEXT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_account_ledger_account_id ON public.account_ledger (account_id);
CREATE INDEX IF NOT EXISTS ix_account_ledger_trade_id ON public.account_ledger (trade_id);
CREATE INDEX IF NOT EXISTS ix_account_ledger_created_at ON public.account_ledger (created_at);
