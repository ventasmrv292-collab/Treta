-- ============================================================
-- Migración 06: risk_profile_id en trades y paper_accounts
-- ============================================================

ALTER TABLE public.trades
    ADD COLUMN IF NOT EXISTS risk_profile_id BIGINT NULL REFERENCES public.risk_profiles(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_trades_risk_profile_id ON public.trades (risk_profile_id);

ALTER TABLE public.paper_accounts
    ADD COLUMN IF NOT EXISTS default_risk_profile_id BIGINT NULL REFERENCES public.risk_profiles(id) ON DELETE SET NULL;
