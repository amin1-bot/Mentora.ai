"""Application settings, read from environment variables (and a local .env file).

Secrets never live in code. Copy .env.example to .env for local development.
"""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Only for local development. Startup refuses this value outside the local environment.
LOCAL_DEV_JWT_SECRET = "local-dev-only-not-a-real-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Mentora API"
    environment: str = "local"  # local | test | staging | production
    api_prefix: str = "/api/v1"
    # Comma-separated list of origins allowed to call the API from a browser.
    cors_origins: str = "http://localhost:5173"
    # Where the React app runs; used to build links in emails (guardian consent).
    frontend_url: str = "http://localhost:5173"
    # Default points at the local Docker database from docker-compose.yml (local dev only).
    database_url: str = "postgresql+asyncpg://mentora:mentora_local_only@localhost:5432/mentora"

    # --- Login tokens ---
    jwt_secret: str = LOCAL_DEV_JWT_SECRET
    access_token_minutes: int = 15
    refresh_token_days: int = 14

    # --- Login protection ---
    max_failed_logins: int = 5
    lockout_minutes: int = 15
    auth_rate_limit_per_minute: int = 10  # per IP address, for signup and login

    # --- Child safety (blueprint section 10) ---
    min_student_age: int = 13
    guardian_consent_required_under: int = 18  # students younger than this need a guardian
    consent_version: str = "2026-11-draft"  # bump when the consent text changes
    guardian_invite_days: int = 7

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _refuse_dev_secret_outside_local(self) -> "Settings":
        if self.environment not in ("local", "test") and self.jwt_secret == LOCAL_DEV_JWT_SECRET:
            raise ValueError("JWT_SECRET must be set to a real secret outside local development")
        if len(self.jwt_secret) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
