-- ============================================================
-- Migración 005: risk_profiles, bot_logs (paper trading bot)
-- Ejecutar después de 001-004.
-- ============================================================

-- Risk profiles: reglas de sizing y límites del bot
CREATE TABLE IF NOT EXISTS public.risk_profiles (
    id                      BIGSERIAL PRIMARY KEY,
    name                    VARCHAR(64) NOT NULL,
    sizing_mode             VARCHAR(32) NOT NULL,
    fixed_quantity          NUMERIC(20, 8) NULL,
    fixed_notional_usdt      NUMERIC(20, 4) NULL,
    risk_pct_per_trade       NUMERIC(8, 4) NULL,
    max_open_positions       INTEGER NOT NULL DEFAULT 5,
    max_margin_pct_of_account NUMERIC(8, 4) NOT NULL DEFAULT 100,
    max_daily_loss_usdt      NUMERIC(20, 4) NULL,
    max_daily_loss_pct       NUMERIC(8, 4) NULL,
    cooldown_after_losses    INTEGER NULL,
    allowed_leverage_json    TEXT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_risk_profiles_updated_at
    BEFORE UPDATE ON public.risk_profiles
    FOR EACH ROW EXECUTE PROCEDURE set_updated_at();

CREATE INDEX IF NOT EXISTS ix_risk_profiles_name ON public.risk_profiles (name);

-- Bot logs / auditoría del bot
CREATE TABLE IF NOT EXISTS public.bot_logs (
    id                      BIGSERIAL PRIMARY KEY,
    level                   VARCHAR(16) NOT NULL DEFAULT 'INFO',
    module                  VARCHAR(64) NOT NULL,
    event_type              VARCHAR(64) NOT NULL,
    message                 TEXT NOT NULL,
    context_json            TEXT NULL,
    related_trade_id        INTEGER NULL REFERENCES public.trades(id) ON DELETE SET NULL,
    related_signal_event_id BIGINT NULL REFERENCES public.signal_events(id) ON DELETE SET NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_bot_logs_event_type ON public.bot_logs (event_type);
CREATE INDEX IF NOT EXISTS ix_bot_logs_created_at ON public.bot_logs (created_at DESC);
CREATE INDEX IF NOT EXISTS ix_bot_logs_related_trade ON public.bot_logs (related_trade_id);
CREATE INDEX IF NOT EXISTS ix_bot_logs_module ON public.bot_logs (module);

-- RLS
ALTER TABLE public.risk_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bot_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow read risk_profiles" ON public.risk_profiles FOR SELECT USING (true);
CREATE POLICY "Allow insert risk_profiles" ON public.risk_profiles FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow update risk_profiles" ON public.risk_profiles FOR UPDATE USING (true);

CREATE POLICY "Allow read bot_logs" ON public.bot_logs FOR SELECT USING (true);
CREATE POLICY "Allow insert bot_logs" ON public.bot_logs FOR INSERT WITH CHECK (true);
