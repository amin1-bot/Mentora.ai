"""Application settings, read from environment variables (and a local .env file).

Secrets never live in code. Copy .env.example to .env for local development.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]

# Only for local development. Startup refuses this value outside the local environment.
LOCAL_DEV_JWT_SECRET = "local-dev-only-not-a-real-secret-change-me"


class Settings(BaseSettings):
    # backend/.env, found the same way whichever folder the server is started from.
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

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

    # --- AI teacher (blueprint section 8) ---
    ai_provider: str = "anthropic"  # "anthropic", "openai_compatible" or "none"
    # Leave empty to let the SDK find credentials (ANTHROPIC_API_KEY or `ant auth login`).
    anthropic_api_key: str | None = None
    # For ai_provider="openai_compatible" (free tiers for development, e.g. Google Gemini).
    # Free tiers may train on requests: made-up test students only, never real ones.
    ai_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    ai_api_key: str | None = None
    ai_reasoning_effort: str | None = None  # sent only if set; not every model supports it
    ai_model: str = "claude-opus-5-5"
    ai_effort: str = "low"  # low | medium | high: thinking depth per reply (speed vs depth)
    ai_max_output_tokens: int = 4000  # per reply, includes the model's thinking
    ai_history_messages: int = 12  # how many recent messages the model sees
    daily_message_limit: int = 150  # per student, protects cost and encourages breaks

    # --- Documents (multi-subject plan, phase 2) ---
    storage_backend: str = "local"  # "local" for now; a private cloud bucket later
    # Private folder for uploads: never served as static files, git-ignored.
    storage_dir: Path = BACKEND_DIR / "storage"
    document_max_mb: int = 25  # per file
    document_max_pages: int = 300
    document_max_count: int = 50  # per student
    document_quota_mb: int = 500  # total per student
    # Uploads start with adults only. Younger students later need a guardian's permission
    # (see documents/permissions.py), so this is the age at which no permission is needed.
    documents_min_age: int = 18
    # Phase 3: reading the text out of uploaded PDFs in the background.
    job_worker_in_api: bool = True  # run the job worker inside the API process (local dev)
    job_poll_seconds: float = 2.0
    document_processing_seconds: int = 180  # give up reading one PDF after this long
    # Phase 4: may students' own documents be sent to the configured AI? Set true only for
    # a paid plan that does not keep or train on inputs. While false, document study works
    # in local development only (for test documents), with a notice on the page.
    ai_private_documents: bool = False
    # Phase 5: quizzes written from a document per student per day (AI cost).
    quiz_daily_limit: int = 10
    # Phase 6: summaries, guides and flashcard sets per student per day (AI cost).
    material_daily_limit: int = 10
    # Phase 7: a TrueType font for PDF exports (Turkish and Cyrillic letters). Empty:
    # DejaVu Sans or Arial is found automatically (see exports/pdf.py).
    pdf_font_path: str = ""

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
