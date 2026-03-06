"""Application configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_database_url(url: str) -> str:
    """Asegura que la URL use el driver asyncpg (Supabase devuelve postgresql://)."""
    if not url.strip():
        return url
    u = url.strip()
    if u.startswith("postgresql://") and not u.startswith("postgresql+asyncpg://"):
        return "postgresql+asyncpg://" + u.split("://", 1)[1]
    return u


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database (Render/Supabase suelen dar postgresql://; lo convertimos a postgresql+asyncpg)
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/crypto_sim"

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

    # Binance
    binance_futures_ws_url: str = "wss://fstream.binance.com/ws"
    binance_futures_rest_url: str = "https://fapi.binance.com"

    # CORS
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
# URL normalizada para SQLAlchemy async (postgresql+asyncpg)
settings.database_url = settings.get_database_url()
