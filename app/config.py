from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str
    database_url: str = "sqlite+aiosqlite:///autoparts.db"
    search_cache_ttl_seconds: float = 60.0
    provider_timeout_seconds: float = 5.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def settings() -> Settings:
    return Settings()
