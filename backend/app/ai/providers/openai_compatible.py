"""Any vendor that speaks the OpenAI "chat completions" format (Google Gemini, Groq, ...).

Used for development on free tiers. Free tiers may use requests to improve the vendor's
products, so they are only for made-up test students, never real ones (blueprint
section 10: no training on student data).

Talks HTTP directly (httpx, already installed with the Anthropic SDK), so no extra SDK.
"""

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

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

# OpenAI finish reasons -> the stop reasons the rest of the app understands.
_STOP_REASONS = {
    "stop": "end_turn",
    "tool_calls": "tool_use",
    "length": "max_tokens",
    "content_filter": "refusal",
}


def _without_additional_properties(schema: Any) -> Any:
    # Some vendors (Gemini) reject "additionalProperties" in tool schemas. The backend
    # validates every board block again, so dropping it here loses nothing.
    if isinstance(schema, dict):
        return {
            k: _without_additional_properties(v)
            for k, v in schema.items()
            if k != "additionalProperties"
        }
    if isinstance(schema, list):
        return [_without_additional_properties(v) for v in schema]
    return schema


BOARD_TOOL = {
    "type": "function",
    "function": {
        "name": BOARD_TOOL_NAME,
        "description": BOARD_TOOL_DESCRIPTION,
        "parameters": _without_additional_properties(BOARD_TOOL_SCHEMA),
    },
}


def _to_openai_messages(request: TurnRequest) -> list[dict[str, str]]:
    # Not every vendor accepts a system message in the middle of the conversation, so the
    # per-turn teaching instruction joins the fixed rules in one leading system message.
    instructions = [m.content for m in request.messages if m.role == "system"]
    system = "\n\n".join([request.system, *instructions])
    chat = [{"role": m.role, "content": m.content} for m in request.messages if m.role != "system"]
    return [{"role": "system", "content": system}, *chat]


class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        model: str,
        reasoning_effort: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,  # tests pass a fake network
    ) -> None:
        self.model = model
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._api_key = api_key
        self._reasoning_effort = reasoning_effort
        self._transport = transport

    async def generate_structured(self, request: StructuredRequest) -> StructuredResult:
        """JSON mode, with the schema in the instructions. Vendors differ in how well they
        follow a schema, so the caller validates every field again."""
        if not self._api_key:
            raise AIProviderError("not_configured")
        system = (
            f"{request.system}\n\nReply with one JSON object only, matching this JSON "
            f"schema exactly:\n{json.dumps(request.schema)}"
        )
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": request.prompt},
            ],
            "max_tokens": request.max_tokens,
            "response_format": {"type": "json_object"},
        }
        if self._reasoning_effort:
            body["reasoning_effort"] = self._reasoning_effort
        try:
            async with httpx.AsyncClient(
                transport=self._transport, timeout=httpx.Timeout(120.0, connect=10.0)
            ) as client:
                response = await client.post(
                    self._url, json=body, headers={"Authorization": f"Bearer {self._api_key}"}
                )
        except httpx.TransportError as exc:
            logger.warning("AI provider connection error: %s", type(exc).__name__)
            raise AIProviderError("unavailable") from exc
        if response.status_code >= 400:
            self._raise_for_status(response)
        try:
            payload = response.json()
            choice = (payload.get("choices") or [{}])[0]
            text = (choice.get("message") or {}).get("content") or ""
        except (ValueError, AttributeError, IndexError) as exc:
            raise AIProviderError("unavailable") from exc
        text = text.strip()
        if text.startswith("`"):  # some models wrap the JSON in a code fence anyway
            text = text.strip("`").removeprefix("json").strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None
        usage = payload.get("usage") or {}
        finish = choice.get("finish_reason") or "stop"
        return StructuredResult(
            data=data,
            model=payload.get("model") or self.model,
            stop_reason=_STOP_REASONS.get(finish, finish),
            tokens_in=usage.get("prompt_tokens") or 0,
            tokens_out=usage.get("completion_tokens") or 0,
        )

    async def stream_turn(self, request: TurnRequest) -> AsyncIterator[ProviderEvent]:
        if not self._api_key:
            raise AIProviderError("not_configured")

        body: dict[str, Any] = {
            "model": self.model,
            "messages": _to_openai_messages(request),
            "max_tokens": request.max_tokens,
            "tools": [BOARD_TOOL],
            "tool_choice": "auto",
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if self._reasoning_effort:
            body["reasoning_effort"] = self._reasoning_effort

        finish_reason: str | None = None
        model = self.model
        tokens_in = tokens_out = 0
        tool_name = ""
        tool_args = ""

        try:
            async with httpx.AsyncClient(
                transport=self._transport, timeout=httpx.Timeout(60.0, connect=10.0)
            ) as client:
                async with client.stream(
                    "POST",
                    self._url,
                    json=body,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                ) as response:
                    if response.status_code >= 400:
                        await response.aread()
                        self._raise_for_status(response)
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        chunk = json.loads(data)
                        model = chunk.get("model") or model
                        if usage := chunk.get("usage"):
                            tokens_in = usage.get("prompt_tokens") or tokens_in
                            tokens_out = usage.get("completion_tokens") or tokens_out
                        for choice in chunk.get("choices") or []:
                            delta = choice.get("delta") or {}
                            if text := delta.get("content"):
                                yield TextDelta(text)
                            # Tool arguments arrive in pieces; only the board tool exists.
                            for call in delta.get("tool_calls") or []:
                                fn = call.get("function") or {}
                                tool_name = fn.get("name") or tool_name
                                tool_args += fn.get("arguments") or ""
                            finish_reason = choice.get("finish_reason") or finish_reason
        except httpx.TransportError as exc:
            logger.warning("AI provider connection error: %s", type(exc).__name__)
            raise AIProviderError("unavailable") from exc
        except json.JSONDecodeError as exc:
            logger.warning("AI provider sent a stream line that is not JSON")
            raise AIProviderError("unavailable") from exc

        if tool_name == BOARD_TOOL_NAME and tool_args:
            try:
                raw = json.loads(tool_args)
            except json.JSONDecodeError as exc:
                logger.warning("Board tool input could not be parsed")
                raise AIProviderError("malformed_output") from exc
            blocks = raw.get("blocks") if isinstance(raw, dict) else None
            # The caller validates every block again before anything reaches the student.
            yield BoardBlocks(blocks if isinstance(blocks, list) else [])

        yield TurnFinished(
            model=model,
            stop_reason=_STOP_REASONS.get(finish_reason or "stop", finish_reason or "end_turn"),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        status = response.status_code
        try:
            payload = response.json()
            if isinstance(payload, list):  # Gemini wraps errors in a list
                payload = payload[0] if payload else {}
            message = str((payload.get("error") or {}).get("message", ""))[:300]
        except (ValueError, AttributeError):
            message = ""
        # The vendor's own reason (bad key, quota, unknown model); safe to log.
        logger.warning("AI provider error %s: %s", status, message)
        # Gemini answers a wrong key with 400 "API key not valid".
        if status in (401, 403) or (status == 400 and "api key" in message.lower()):
            raise AIProviderError("not_configured")
        if status == 429:
            raise AIProviderError("rate_limited")
        raise AIProviderError("unavailable")
