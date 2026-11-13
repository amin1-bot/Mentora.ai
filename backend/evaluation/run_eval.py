"""Run the teacher evaluation against a real model.

    cd backend
    python -m evaluation.run_eval                      # model from settings
    python -m evaluation.run_eval --model claude-sonnet-5-5 --effort low
    python -m evaluation.run_eval --repeat 3           # each case 3 times

This calls the real API and costs money (a few cents per full run at today's prices).
Each run writes evaluation/reports/<timestamp>-<model>.json and prints a summary.

Metrics (blueprint section 12):
- raw leak rate: replies where the MODEL tried to reveal a hidden answer (the guard
  caught it). This compares models and prompts. Target: under 5%.
- final leak rate: replies where a hidden answer reached the student anyway, including
  answers spelled in words, which the guard does not catch. Should be 0.
- fallbacks: replies replaced by a fixed line (two leaks in a row, refusal, outage).
- valid board: share of whiteboard blocks that passed validation.
- first text: time until the first words appear. Target: under 2 seconds.
"""

import argparse
import asyncio
import json
import re
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from app.ai.base import AIProvider, TurnRequest
from app.core.config import get_settings
from app.modules.adaptive.answers import check_answer, parse_number
from app.modules.adaptive.engine import LessonState, decide
from app.modules.curriculum.seed_data import MISCONCEPTIONS, QUESTIONS
from app.modules.teacher.generate import GenerationResult, generate_reply
from app.modules.teacher.prompts import SYSTEM_RULES, QuestionInfo, TurnContext, build_messages
from evaluation.cases import CASES, Case

# Approximate prices in USD per million tokens (input, output), November 2026.
PRICES = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
}

_WORDS = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen"
).split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def number_words(n: float) -> str | None:
    """'20' -> 'twenty', '42' -> 'forty-two' (whole numbers below 100 only)."""
    if n != int(n) or not 0 <= n < 100:
        return None
    n = int(n)
    if n < 20:
        return _WORDS[n]
    return _TENS[n // 10] + ("" if n % 10 == 0 else f"-{_WORDS[n % 10]}")


_UNITS = "one|two|three|four|five|six|seven|eight|nine"


def word_leak(text: str, protected: list[float]) -> bool:
    lowered = text.lower()
    for p in protected:
        words = number_words(p)
        # "twenty" must not match inside "twenty-five".
        pattern = rf"\b{words.replace('-', '[- ]')}\b(?![- ](?:{_UNITS})\b)" if words else None
        if pattern and re.search(pattern, lowered):
            return True
    return False


def _question(percent: float, of: float) -> dict:
    for q in QUESTIONS:
        if q["answer_data"]["percent"] == percent and q["answer_data"]["of"] == of:
            return q
    raise ValueError(f"no seeded question {percent}% of {of}")


@dataclass
class CaseResult:
    case: str
    action: str
    text: str
    board_blocks: int
    blocked_leaks: int
    final_leak: bool
    word_leak: bool
    fallback: str | None
    first_text_ms: int | None
    tokens_in: int
    tokens_out: int


async def run_case(provider: AIProvider, case: Case, grade: int = 8) -> CaseResult:
    current = _question(*case.question) if case.question else None
    state = LessonState(
        has_question=current is not None,
        hint_level=case.hint_level,
        attempts_on_current=case.attempts,
        wrong_on_current=case.wrong,
        difficulty=3,
    )
    check = None
    misconception = None
    if case.event == "answer" and current and case.text:
        value = parse_number(case.text)
        check = check_answer(current["answer_data"], value) if value is not None else None
        if check and check.misconception_code:
            misconception = next(
                m["description"] for m in MISCONCEPTIONS if m["code"] == check.misconception_code
            )
    decision = decide(state, case.event, check)  # type: ignore[arg-type]
    next_q = None
    if decision.ask_new_question:
        exclude = current["id"] if current else None
        answer = current["answer_data"]["value"] if current else None
        next_q = next(
            q
            for q in QUESTIONS
            if q["difficulty"] == decision.state.difficulty
            and q["id"] != exclude
            and q["answer_data"]["value"] != answer
        )

    def info(q: dict | None) -> QuestionInfo | None:
        return QuestionInfo(q["text"], float(q["answer_data"]["value"])) if q else None

    protected = []
    if current and not decision.reveal_current_answer:
        protected.append(float(current["answer_data"]["value"]))
    if next_q:
        protected.append(float(next_q["answer_data"]["value"]))

    history = [{"role": r, "content": t} for r, t in case.history]
    if case.event == "hint":
        history.append({"role": "student", "content": "Give me a hint"})
    elif case.event == "dont_get_it":
        history.append({"role": "student", "content": "I don't get it"})
    elif case.text:
        history.append({"role": "student", "content": case.text})

    ctx = TurnContext(
        decision=decision,
        grade_level=grade,
        topic_name="Percentages",
        current=info(current),
        next_question=info(next_q),
        student_answer=check.value if check else None,
        misconception=misconception,
    )

    def build(stricter: bool) -> TurnRequest:
        from dataclasses import replace

        return TurnRequest(
            SYSTEM_RULES,
            build_messages(history, replace(ctx, stricter=stricter)),
            get_settings().ai_max_output_tokens,
        )

    result = GenerationResult()
    async for _ in generate_reply(provider, build, protected, result):
        pass

    from app.modules.teacher.guard import contains_any

    board_text = json.dumps(result.board)
    return CaseResult(
        case=case.id,
        action=decision.action,
        text=result.text,
        board_blocks=len(result.board),
        blocked_leaks=result.blocked_leaks,
        final_leak=contains_any(result.text + board_text, protected),
        word_leak=word_leak(result.text + board_text, protected),
        fallback=result.fallback,
        first_text_ms=result.first_text_ms,
        tokens_in=sum(u.tokens_in for u in result.usage),
        tokens_out=sum(u.tokens_out for u in result.usage),
    )


def summarize(results: list[CaseResult], model: str) -> dict:
    n = len(results)
    first = [r.first_text_ms for r in results if r.first_text_ms is not None]
    tin, tout = sum(r.tokens_in for r in results), sum(r.tokens_out for r in results)
    price = PRICES.get(model)
    return {
        "model": model,
        "replies": n,
        "raw_leak_rate": sum(r.blocked_leaks > 0 for r in results) / n if n else 0,
        "final_leak_rate": sum(r.final_leak or r.word_leak for r in results) / n if n else 0,
        "word_leaks": sum(r.word_leak for r in results),
        "fallbacks": sum(r.fallback is not None for r in results),
        "median_first_text_ms": statistics.median(first) if first else None,
        "tokens_in": tin,
        "tokens_out": tout,
        "estimated_cost_usd": round((tin * price[0] + tout * price[1]) / 1e6, 4) if price else None,
    }


async def run(
    provider: AIProvider, model: str, repeat: int = 1, cases: list[Case] | None = None
) -> tuple[dict, list[CaseResult]]:
    results = []
    for _ in range(repeat):
        for case in cases or CASES:
            results.append(await run_case(provider, case))
    return summarize(results, model), results


def main() -> None:
    from app.ai.providers.anthropic_provider import AnthropicProvider

    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--model", default=settings.ai_model)
    parser.add_argument("--effort", default=settings.ai_effort)
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()

    provider = AnthropicProvider(
        model=args.model, effort=args.effort, api_key=settings.anthropic_api_key
    )
    summary, results = asyncio.run(run(provider, args.model, args.repeat))
    summary["effort"] = args.effort

    out_dir = Path(__file__).parent / "reports"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"{time.strftime('%Y%m%d-%H%M%S')}-{args.model}.json"
    path.write_text(
        json.dumps({"summary": summary, "results": [asdict(r) for r in results]}, indent=2),
        encoding="utf-8",
    )

    for r in results:
        flag = "LEAK" if r.final_leak or r.word_leak else ("blocked" if r.blocked_leaks else "ok")
        print(f"{flag:8} {r.case:28} {r.action:20} {r.text[:70]!r}")
    print(json.dumps(summary, indent=2))
    print(f"Report: {path}")


if __name__ == "__main__":
    main()
