"""One teacher reply through the scripted provider, guard and board validator."""

import asyncio

from app.ai.base import ChatMessage, TurnRequest
from app.modules.teacher.generate import Delta, GenerationResult, Reset, generate_reply
from app.tests.fakes import Reply, ScriptedProvider


def _run(provider: ScriptedProvider, protected: list[float]) -> tuple[list, GenerationResult]:
    result = GenerationResult()
    stricter_flags: list[bool] = []

    def build(stricter: bool) -> TurnRequest:
        stricter_flags.append(stricter)
        return TurnRequest("rules", [ChatMessage("user", "hi")], 100)

    async def collect() -> list:
        return [e async for e in generate_reply(provider, build, protected, result)]

    events = asyncio.run(collect())
    result.raw_leak_texts.append(str(stricter_flags))  # expose flags to the tests
    return events, result


def _shown(events: list) -> str:
    text = ""
    for e in events:
        text = "" if isinstance(e, Reset) else text + (e.text if isinstance(e, Delta) else "")
    return text


def test_clean_reply_with_valid_board() -> None:
    provider = ScriptedProvider(
        [
            Reply(
                ["Percent means ", "out of 100."],
                board=[
                    {"type": "step", "content": "Write 25% as 25/100"},
                    {"type": "equation", "content": "\\frac{25}{100}"},
                    {"type": "html", "content": "<b>bad</b>"},
                ],
            )
        ]
    )
    events, result = _run(provider, [20])
    assert _shown(events) == "Percent means out of 100."
    assert result.text == "Percent means out of 100."
    assert result.board == [
        {"type": "step", "number": 1, "text": "Write 25% as 25/100"},
        {"type": "equation", "latex": "\\frac{25}{100}"},
    ]
    assert result.blocked_leaks == 0 and result.fallback is None


def test_leaking_draft_is_reset_and_regenerated_with_a_stricter_instruction() -> None:
    provider = ScriptedProvider(
        [
            Reply(["Good try. ", "It is 2", "0 actually."]),
            Reply(["Good try. ", "Remember to divide by 100."]),
        ]
    )
    events, result = _run(provider, [20])
    assert any(isinstance(e, Reset) for e in events)
    assert _shown(events) == "Good try. Remember to divide by 100."
    assert "20" not in "".join(e.text for e in events if isinstance(e, Delta))
    assert result.blocked_leaks == 1
    assert result.raw_leak_texts[-1] == "[False, True]"  # second attempt was stricter


def test_two_leaks_fall_back_to_a_safe_line_written_by_code() -> None:
    provider = ScriptedProvider([Reply(["It's 20."]), Reply(["The answer: 20"])])
    events, result = _run(provider, [20])
    assert result.fallback == "leak"
    assert "20" not in _shown(events)
    assert result.blocked_leaks == 2


def test_board_cannot_leak_either() -> None:
    provider = ScriptedProvider(
        [Reply(["Look at the board."], board=[{"type": "equation", "content": "x = 20"}])]
    )
    _, result = _run(provider, [20])
    assert result.board == []
    assert result.board_blocks_dropped == 1


def test_refusal_uses_a_fixed_line() -> None:
    provider = ScriptedProvider([Reply(["I can't"], stop_reason="refusal")])
    events, result = _run(provider, [20])
    assert result.fallback == "refusal"
    assert "back to our lesson" in _shown(events)


def test_provider_outage_is_reported() -> None:
    provider = ScriptedProvider([Reply([], error="unavailable")])
    _, result = _run(provider, [20])
    assert result.fallback == "unavailable"


def test_board_only_reply_gets_a_spoken_line() -> None:
    provider = ScriptedProvider(
        [Reply([], board=[{"type": "step", "content": "Write 25% as a fraction"}])]
    )
    events, result = _run(provider, [20])
    assert _shown(events) == "Have a look at the board."
    assert result.board == [{"type": "step", "number": 1, "text": "Write 25% as a fraction"}]
    assert result.fallback is None


def test_completely_empty_reply_is_never_shown_empty() -> None:
    events, result = _run(ScriptedProvider([Reply(["   "])]), [20])
    assert (
        _shown(events) == "Let's take it one step at a time. What do you think the first step is?"
    )
    assert result.fallback == "empty" and result.board == []
