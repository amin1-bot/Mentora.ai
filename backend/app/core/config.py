"""Application settings, read from environment variables (and a local .env file).

Secrets never live in code. Copy .env.example to .env for local development.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Mentora API"
    environment: str = "local"  # local | staging | production
    api_prefix: str = "/api/v1"
    # Comma-separated list of origins allowed to call the API from a browser.
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
