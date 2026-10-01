from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str
    database_url: str = "sqlite+aiosqlite:///autoparts.db"
    log_level: str = "INFO"
    search_cache_backend: str = "memory"
    redis_url: str | None = None
    search_cache_ttl_seconds: float = 60.0
    provider_timeout_seconds: float = 5.0
    provider_circuit_failure_threshold: int = 3
    provider_circuit_cooldown_seconds: float = 60.0
    external_provider_enabled: bool = False
    external_provider_name: str = "Partner API"
    external_provider_base_url: str | None = None
    external_provider_search_path: str = "/search"
    external_provider_api_key: str | None = None
    external_provider_api_key_header: str = "Authorization"
    external_provider_auth_scheme: str = "Bearer"
    external_provider_allow_http: bool = False
    demo_provider_enabled: bool = True
    demo_fitment_enabled: bool = True
    fitment_api_enabled: bool = False
    fitment_api_base_url: str | None = None
    fitment_api_resolve_path: str = "/fitment/resolve"
    fitment_api_key: str | None = None
    fitment_api_key_header: str = "Authorization"
    fitment_api_auth_scheme: str = "Bearer"
    fitment_api_allow_http: bool = False
    vehicle_api_enabled: bool = False
    vehicle_api_base_url: str | None = None
    vehicle_api_vin_path: str = "/vehicle/vin"
    vehicle_api_key: str | None = None
    vehicle_api_key_header: str = "Authorization"
    vehicle_api_auth_scheme: str = "Bearer"
    vehicle_api_allow_http: bool = False
    price_alerts_enabled: bool = True
    price_alert_worker_mode: str = "embedded"
    price_alert_interval_seconds: int = 3600
    price_alert_drop_percent: float = 5.0
    bot_run_mode: str = "polling"
    webhook_url: str | None = None
    webhook_path: str = "/webhook"
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8080
    webhook_secret_token: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def settings() -> Settings:
    return Settings()
