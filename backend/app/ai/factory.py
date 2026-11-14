"""Picks the configured AI provider. Tests replace this dependency with a scripted fake
that lives only in the test folder; the product never ships a fake teacher."""

from functools import lru_cache

from app.ai.base import AIProvider
from app.core.config import Settings, get_settings


def build_provider(
    s: Settings, *, model: str | None = None, effort: str | None = None
) -> AIProvider | None:
    """The provider the settings ask for (model/effort can be overridden, e.g. by evals)."""
    if s.ai_provider == "anthropic":
        from app.ai.providers.anthropic_provider import AnthropicProvider

        # An empty ANTHROPIC_API_KEY= line means "not set": let the SDK use `ant auth login`.
        return AnthropicProvider(
            model=model or s.ai_model,
            effort=effort or s.ai_effort,
            api_key=s.anthropic_api_key or None,
        )
    if s.ai_provider == "openai_compatible":
        from app.ai.providers.openai_compatible import OpenAICompatibleProvider

        return OpenAICompatibleProvider(
            base_url=s.ai_base_url,
            api_key=s.ai_api_key or None,
            model=model or s.ai_model,
            reasoning_effort=effort or s.ai_reasoning_effort,
        )
    return None


@lru_cache
def _configured() -> AIProvider | None:
    return build_provider(get_settings())


def get_ai_provider() -> AIProvider | None:
    """FastAPI dependency. None means no provider is configured (the API says so clearly)."""
    return _configured()
