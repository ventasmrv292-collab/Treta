"""Application configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/crypto_sim"

    # App
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True

    # Binance
    binance_futures_ws_url: str = "wss://fstream.binance.com/ws"
    binance_futures_rest_url: str = "https://fapi.binance.com"

    # CORS
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
