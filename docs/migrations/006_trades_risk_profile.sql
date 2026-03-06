-- Añadir risk_profile_id a trades (opcional por operación)
ALTER TABLE public.trades
ADD COLUMN IF NOT EXISTS risk_profile_id BIGINT NULL REFERENCES public.risk_profiles(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_trades_risk_profile_id ON public.trades (risk_profile_id);

-- Opcional: perfil de riesgo por defecto en cuenta paper
ALTER TABLE public.paper_accounts
ADD COLUMN IF NOT EXISTS default_risk_profile_id BIGINT NULL REFERENCES public.risk_profiles(id) ON DELETE SET NULL;