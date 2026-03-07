-- ============================================================
-- Migración 02: ALTER trades (account_id, signal_event_id, status, margen, ledger, idempotency)
-- ============================================================

ALTER TABLE public.trades
    ADD COLUMN IF NOT EXISTS account_id BIGINT NULL REFERENCES public.paper_accounts(id),
    ADD COLUMN IF NOT EXISTS signal_event_id BIGINT NULL REFERENCES public.signal_events(id),
    ADD COLUMN IF NOT EXISTS status VARCHAR(16) NOT NULL DEFAULT 'OPEN',
    ADD COLUMN IF NOT EXISTS opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS margin_used_usdt NUMERIC(20, 4) NULL,
    ADD COLUMN IF NOT EXISTS capital_before_usdt NUMERIC(20, 4) NULL,
    ADD COLUMN IF NOT EXISTS capital_after_usdt NUMERIC(20, 4) NULL,
    ADD COLUMN IF NOT EXISTS fee_config_id INTEGER NULL REFERENCES public.fee_configs(id),
    ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(128) NULL;

CREATE INDEX IF NOT EXISTS ix_trades_status ON public.trades (status);
CREATE INDEX IF NOT EXISTS ix_trades_account_id ON public.trades (account_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_trades_idempotency
    ON public.trades (idempotency_key) WHERE idempotency_key IS NOT NULL;
