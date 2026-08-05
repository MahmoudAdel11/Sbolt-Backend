from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    app_name: str = "Yalla Go Backend"
    app_env: str = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # Database
    database_url: str
    db_echo: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # Security
    secret_key: str
    access_token_expire_minutes: int = 30
    algorithm: str = "HS256"

    # Logging
    log_level: str = "INFO"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # Rate limiting
    rate_limit_default: str = "100/minute"
    rate_limit_auth: str = "5/minute"


@lru_cache
def get_settings() -> Settings:
    return Settings()
