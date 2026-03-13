"""Application configuration."""
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_database_url(url: str) -> str:
    """Limpia y convierte postgresql:// a postgresql+asyncpg:// (Supabase/Render)."""
    if not url or not isinstance(url, str):
        return url or ""
    u = url.strip().strip('"').strip("'")
    if not u:
        return url
    if u.startswith("postgresql://") and "+asyncpg" not in u[:20]:
        u = "postgresql+asyncpg://" + u.split("://", 1)[1]
    return u


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database (Render/Supabase suelen dar postgresql://; lo convertimos a postgresql+asyncpg)
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/crypto_sim"

    @field_validator("database_url", mode="before")
    @classmethod
    def clean_database_url(cls, v: str | None) -> str:
        if v is None:
            return "postgresql+asyncpg://postgres:postgres@localhost:5432/crypto_sim"
        return _normalize_database_url(str(v))

    def get_database_url(self) -> str:
        return _normalize_database_url(self.database_url)

    # App (Render inyecta PORT; en local usamos 8000)
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True

    @property
    def port(self) -> int:
        import os
        return int(os.environ.get("PORT", self.api_port))

    # Binance (si en tu host da 451, prueba otra región de despliegue o BINANCE_FUTURES_REST_URL)
    binance_futures_ws_url: str = "wss://fstream.binance.com/ws"
    binance_futures_rest_url: str = "https://fapi.binance.com"
    # Si True, no se usa nunca CoinGecko: solo Binance/Bybit; si ambos fallan, falla.
    binance_only: bool = False
    # Si True, se intenta Bybit primero; si falla, Binance. Recomendado si Binance da 451/418 en tu región.
    bybit_first: bool = False
    # Si True, tras fallar Bybit y Binance se intenta CoinGecko como último recurso. Por defecto False (solo Bybit + Binance).
    allow_coingecko_fallback: bool = False

    # CORS: orígenes permitidos separados por coma (ej. https://tu-app.vercel.app).
    # En Railway/Render define CORS_ORIGINS con la URL de tu frontend en Vercel.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Si True, permite cualquier subdominio de vercel.app (preview y producción).
    cors_allow_vercel_app: bool = True

    @property
    def cors_origins_list(self) -> list[str]:
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return origins

    # Regex para permitir *.vercel.app (usado por el middleware si cors_allow_vercel_app=True).
    cors_vercel_regex: str = r"https://[a-z0-9-]+\.vercel\.app"

    # Pushover: notificaciones al abrir/cerrar operaciones (opcional).
    pushover_user_key: str = ""
    pushover_app_token: str = ""


settings = Settings()
