"""Picks the configured AI provider. Tests replace this dependency with a scripted fake
that lives only in the test folder; the product never ships a fake teacher."""

from functools import lru_cache

from app.ai.base import AIProvider
from app.core.config import get_settings


@lru_cache
def _anthropic() -> AIProvider:
    from app.ai.providers.anthropic_provider import AnthropicProvider

    s = get_settings()
    return AnthropicProvider(model=s.ai_model, effort=s.ai_effort, api_key=s.anthropic_api_key)


def get_ai_provider() -> AIProvider | None:
    """FastAPI dependency. None means no provider is configured (the API says so clearly)."""
    s = get_settings()
    if s.ai_provider == "anthropic":
        return _anthropic()
    return None
