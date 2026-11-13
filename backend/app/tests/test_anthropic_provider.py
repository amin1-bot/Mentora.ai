"""The Claude provider's error handling, without network access or an API key."""

import asyncio

import pytest

from app.ai.base import AIProviderError, ChatMessage, TurnRequest
from app.ai.providers.anthropic_provider import AnthropicProvider


def _run_once() -> None:
    provider = AnthropicProvider(model="claude-opus-5-5", effort="low", api_key=None)

    async def run() -> None:
        request = TurnRequest("rules", [ChatMessage("user", "hi")], 100)
        async for _ in provider.stream_turn(request):
            pass

    asyncio.run(run())


@pytest.fixture
def no_credentials(monkeypatch: pytest.MonkeyPatch, tmp_path) -> pytest.MonkeyPatch:
    for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return monkeypatch


def test_no_credentials_at_all_is_not_configured(no_credentials: pytest.MonkeyPatch) -> None:
    with pytest.raises(AIProviderError, match="not_configured"):
        _run_once()


def test_unusable_login_profile_is_not_configured(
    no_credentials: pytest.MonkeyPatch, tmp_path
) -> None:
    no_credentials.setenv("ANTHROPIC_CONFIG_DIR", str(tmp_path / "missing"))
    with pytest.raises(AIProviderError, match="not_configured"):
        _run_once()
