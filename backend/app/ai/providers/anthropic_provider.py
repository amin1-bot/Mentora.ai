"""Claude (Anthropic) implementation of the AI provider interface."""

import json
import logging
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager

import anthropic

from app.ai.base import (
    BOARD_TOOL_DESCRIPTION,
    BOARD_TOOL_NAME,
    BOARD_TOOL_SCHEMA,
    AIProviderError,
    BoardBlocks,
    ProviderEvent,
    StructuredRequest,
    StructuredResult,
    TextDelta,
    TurnFinished,
    TurnRequest,
)

logger = logging.getLogger(__name__)

# Server-side fallback: if the main model declines a request for safety reasons, the API
# re-runs it on a suitable fallback model within the same call.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, *, model: str, effort: str, api_key: str | None = None) -> None:
        self.model = model
        self.effort = effort
        self._api_key = api_key
        self._client: anthropic.AsyncAnthropic | None = None

    def _get_client(self) -> anthropic.AsyncAnthropic:
        # Created on first use, so a credentials problem is reported like any other error.
        # api_key=None lets the SDK find credentials itself (ANTHROPIC_API_KEY, profile).
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(
                api_key=self._api_key, max_retries=2, timeout=60.0
            )
        return self._client

    async def generate_structured(self, request: StructuredRequest) -> StructuredResult:
        """Schema-constrained JSON (output_config.format). Streamed, because quiz answers
        can be long; only the final message is used."""
        with _mapped_errors():
            async with self._get_client().messages.stream(
                model=self.model,
                max_tokens=request.max_tokens,
                system=[
                    {"type": "text", "text": request.system, "cache_control": {"type": "ephemeral"}}
                ],
                messages=[{"role": "user", "content": request.prompt}],
                output_config={
                    "effort": self.effort,
                    "format": {"type": "json_schema", "schema": request.schema},
                },
            ) as stream:
                final = await stream.get_final_message()
        text = next((b.text for b in final.content if b.type == "text"), "")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None  # e.g. cut off at max_tokens; the caller treats it as a failure
        usage = final.usage
        return StructuredResult(
            data=data,
            model=final.model,
            stop_reason=final.stop_reason or "end_turn",
            tokens_in=usage.input_tokens
            + (usage.cache_read_input_tokens or 0)
            + (usage.cache_creation_input_tokens or 0),
            tokens_out=usage.output_tokens,
        )

    async def stream_turn(self, request: TurnRequest) -> AsyncIterator[ProviderEvent]:
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        try:
            async with self._get_client().beta.messages.stream(
                model=self.model,
                max_tokens=request.max_tokens,
                # The fixed teaching rules never change, so they are cached between turns.
                system=[
                    {"type": "text", "text": request.system, "cache_control": {"type": "ephemeral"}}
                ],
                messages=messages,
                tools=[
                    {
                        "name": BOARD_TOOL_NAME,
                        "description": BOARD_TOOL_DESCRIPTION,
                        "input_schema": BOARD_TOOL_SCHEMA,
                        "strict": True,
                        "eager_input_streaming": True,
                    }
                ],
                tool_choice={"type": "auto"},
                output_config={"effort": self.effort},
                betas=[FALLBACK_BETA],
                fallbacks="default",
            ) as stream:
                async for event in stream:
                    if event.type == "text":
                        yield TextDelta(event.text)
                final = await stream.get_final_message()
        except ValueError as exc:  # board tool JSON the SDK could not parse at all
            logger.warning("Board tool input could not be parsed: %s", exc)
            raise AIProviderError("malformed_output") from exc
        except TypeError as exc:
            # The SDK raises TypeError when no API key or login profile can be found.
            if "authentication" in str(exc).lower():
                raise AIProviderError("not_configured") from exc
            raise
        except anthropic.RateLimitError as exc:
            raise AIProviderError("rate_limited") from exc
        except (
            anthropic.AuthenticationError,
            anthropic.PermissionDeniedError,
            anthropic.CredentialsError,  # a login profile is configured but unusable
        ) as exc:
            raise AIProviderError("not_configured") from exc
        except anthropic.APIStatusError as exc:
            # The API's own reason (e.g. "credit balance is too low"); it never contains
            # anything the student wrote, so it is safe to log.
            logger.warning("AI provider error %s: %s", exc.status_code, exc.message)
            raise AIProviderError("unavailable") from exc
        except anthropic.APIConnectionError as exc:
            logger.warning("AI provider connection error: %s", type(exc).__name__)
            raise AIProviderError("unavailable") from exc
        except anthropic.AnthropicError as exc:
            logger.warning("AI provider error: %s", type(exc).__name__)
            raise AIProviderError("unavailable") from exc

        for block in final.content:
            if block.type == "tool_use" and block.name == BOARD_TOOL_NAME:
                raw = block.input if isinstance(block.input, dict) else {}
                blocks = raw.get("blocks")
                # The tolerant streaming parser can return partial input; the caller
                # validates every block again before anything reaches the student.
                yield BoardBlocks(blocks if isinstance(blocks, list) else [])
                break

        usage = final.usage
        tokens_in = (
            usage.input_tokens
            + (usage.cache_read_input_tokens or 0)
            + (usage.cache_creation_input_tokens or 0)
        )
        yield TurnFinished(
            model=final.model,
            stop_reason=final.stop_reason or "end_turn",
            tokens_in=tokens_in,
            tokens_out=usage.output_tokens,
        )


@contextmanager
def _mapped_errors() -> Iterator[None]:
    """The same error mapping as stream_turn, for structured calls."""
    try:
        yield
    except TypeError as exc:
        if "authentication" in str(exc).lower():
            raise AIProviderError("not_configured") from exc
        raise
    except anthropic.RateLimitError as exc:
        raise AIProviderError("rate_limited") from exc
    except (
        anthropic.AuthenticationError,
        anthropic.PermissionDeniedError,
        anthropic.CredentialsError,
    ) as exc:
        raise AIProviderError("not_configured") from exc
    except anthropic.APIStatusError as exc:
        logger.warning("AI provider error %s: %s", exc.status_code, exc.message)
        raise AIProviderError("unavailable") from exc
    except anthropic.AnthropicError as exc:
        logger.warning("AI provider error: %s", type(exc).__name__)
        raise AIProviderError("unavailable") from exc
