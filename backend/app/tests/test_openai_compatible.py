"""The OpenAI-compatible provider (Gemini, Groq), against a fake network: no real calls."""

import asyncio
import json

import httpx
import pytest

from app.ai.base import (
    AIProviderError,
    BoardBlocks,
    ChatMessage,
    TextDelta,
    TurnFinished,
    TurnRequest,
)
from app.ai.providers.openai_compatible import OpenAICompatibleProvider

REQUEST = TurnRequest(
    "RULES",
    [
        ChatMessage("user", "hi"),
        ChatMessage("assistant", "hello"),
        ChatMessage("user", "what is 10% of 50?"),
        ChatMessage("system", "INSTRUCTION"),
    ],
    500,
)


def _sse(*chunks: dict) -> bytes:
    lines = [f"data: {json.dumps(c)}\n\n" for c in chunks] + ["data: [DONE]\n\n"]
    return "".join(lines).encode()


def _run(handler, api_key: str | None = "test-key", effort: str | None = None) -> list:
    provider = OpenAICompatibleProvider(
        base_url="https://example.test/v1/",
        api_key=api_key,
        model="test-model",
        reasoning_effort=effort,
        transport=httpx.MockTransport(handler),
    )

    async def collect() -> list:
        return [e async for e in provider.stream_turn(REQUEST)]

    return asyncio.run(collect())


def test_streams_text_board_and_usage() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        args = json.dumps({"blocks": [{"type": "equation", "content": "10\\% \\times 50"}]})
        body = _sse(
            {"model": "test-model-001", "choices": [{"delta": {"content": "Let's "}}]},
            {"choices": [{"delta": {"content": "think."}}]},
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "function": {"name": "write_on_board", "arguments": args[:9]},
                                }
                            ]
                        }
                    }
                ]
            },
            {
                "choices": [
                    {"delta": {"tool_calls": [{"index": 0, "function": {"arguments": args[9:]}}]}}
                ]
            },  # noqa: E501
            {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
            {"choices": [], "usage": {"prompt_tokens": 120, "completion_tokens": 30}},
        )
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    events = _run(handler)

    assert seen["url"] == "https://example.test/v1/chat/completions"
    assert seen["auth"] == "Bearer test-key"
    messages = seen["body"]["messages"]
    # The per-turn instruction joins the rules in one leading system message.
    assert messages[0] == {"role": "system", "content": "RULES\n\nINSTRUCTION"}
    assert [m["role"] for m in messages[1:]] == ["user", "assistant", "user"]
    assert "reasoning_effort" not in seen["body"]
    assert "additionalProperties" not in json.dumps(seen["body"]["tools"])

    assert events[:2] == [TextDelta("Let's "), TextDelta("think.")]
    assert events[2] == BoardBlocks([{"type": "equation", "content": "10\\% \\times 50"}])
    assert events[3] == TurnFinished("test-model-001", "tool_use", 120, 30)


def test_reasoning_effort_is_sent_only_when_set() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, content=_sse({"choices": [{"delta": {"content": "ok"}}]}))

    events = _run(handler, effort="low")
    assert seen["body"]["reasoning_effort"] == "low"
    assert events[-1] == TurnFinished("test-model", "end_turn", 0, 0)


def test_missing_key_is_not_configured_without_calling() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not call the network")

    with pytest.raises(AIProviderError, match="not_configured"):
        _run(handler, api_key=None)


@pytest.mark.parametrize(
    ("status", "payload", "code"),
    [
        (401, {"error": {"message": "bad key"}}, "not_configured"),
        (
            400,
            [{"error": {"message": "API key not valid. Please pass a valid API key."}}],
            "not_configured",
        ),  # noqa: E501
        (429, {"error": {"message": "quota"}}, "rate_limited"),
        (404, {"error": {"message": "model not found"}}, "unavailable"),
        (500, {}, "unavailable"),
    ],
)
def test_http_errors_map_to_codes(status: int, payload, code: str) -> None:
    with pytest.raises(AIProviderError, match=code):
        _run(lambda request: httpx.Response(status, json=payload))


def test_connection_error_is_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    with pytest.raises(AIProviderError, match="unavailable"):
        _run(handler)


def test_broken_board_json_is_malformed_output() -> None:
    body = _sse(
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "function": {"name": "write_on_board", "arguments": "{oops"},
                            }
                        ]
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        }
    )
    with pytest.raises(AIProviderError, match="malformed_output"):
        _run(lambda request: httpx.Response(200, content=body))
