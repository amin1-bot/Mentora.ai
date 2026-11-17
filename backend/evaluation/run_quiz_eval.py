"""Quiz generation evaluation (multi-subject plan, phase 5 gate).

    cd backend
    python -m evaluation.run_quiz_eval                 # model from settings
    python -m evaluation.run_quiz_eval --runs 3 --pause 8

Writes quizzes from the made-up sample document in run_grounding_eval.py (never a student
upload, so it is safe on a free plan) and checks every question with the same code the
app uses. Writes evaluation/reports/<timestamp>-quiz-<model>.json.

Metrics:
- acceptance rate: questions that pass every code check, out of those written.
  Rejected ones are dropped (and asked for once more in the app). Target: over 85%.
- rejection reasons: which rule failed, to improve the prompt.
- type mix: whether the model wrote the types asked for.
"""

import argparse
import asyncio
import json
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from app.ai.base import AIProvider, StructuredRequest
from app.ai.factory import build_provider
from app.core.config import get_settings
from app.modules.quizzes.generation import SCHEMA, SYSTEM, build_prompt, check_items, type_plan
from evaluation.run_grounding_eval import PAGES, TITLE

TYPES = ["multiple_choice", "true_false", "fill_blank"]


@dataclass(frozen=True)
class _Page:
    page_number: int
    text: str


async def one_run(provider: AIProvider, count: int, difficulty: str) -> dict:
    pages = [_Page(n, t) for n, t in PAGES.items()]
    request = StructuredRequest(
        system=SYSTEM,
        prompt=build_prompt(TITLE, pages, type_plan(count, TYPES), difficulty, []),  # type: ignore[arg-type]
        schema=SCHEMA,
        max_tokens=max(3000, 450 * count + 1500),
    )
    started = time.monotonic()
    result = await provider.generate_structured(request)
    seconds = round(time.monotonic() - started, 1)
    report = check_items(result.data, allowed_types=set(TYPES), page_texts=dict(PAGES))
    written = len(report.accepted) + sum(report.rejected.values())
    return {
        "difficulty": difficulty,
        "asked": count,
        "written": written,
        "accepted": len(report.accepted),
        "rejected": dict(report.rejected),
        "types": dict(Counter(q.question_type for q in report.accepted)),
        "seconds": seconds,
        "tokens": [result.tokens_in, result.tokens_out],
        "questions": [
            {
                "type": q.question_type,
                "prompt": q.prompt,
                "answer": q.answer_data,
                "pages": q.source_pages,
                "explanation": q.explanation,
            }
            for q in report.accepted
        ],
    }


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--model", default=settings.ai_model)
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--count", type=int, default=8)
    parser.add_argument("--pause", type=float, default=0.0)
    args = parser.parse_args()
    provider = build_provider(settings, model=args.model)
    if provider is None:
        raise SystemExit("No AI provider configured (AI_PROVIDER in backend/.env).")

    async def run_all() -> list[dict]:
        out = []
        for i in range(args.runs):
            if i and args.pause:
                await asyncio.sleep(args.pause)
            difficulty = ["mixed", "hard", "easy"][i % 3]
            r = await one_run(provider, args.count, difficulty)
            print(
                f"run {i + 1} ({difficulty}): {r['accepted']}/{r['written']} accepted, "
                f"rejected {r['rejected']}, {r['seconds']} s"
            )
            out.append(r)
        return out

    runs = asyncio.run(run_all())
    written = sum(r["written"] for r in runs)
    accepted = sum(r["accepted"] for r in runs)
    reasons: Counter[str] = Counter()
    for r in runs:
        reasons.update(r["rejected"])
    summary = {
        "model": args.model,
        "runs": len(runs),
        "asked": sum(r["asked"] for r in runs),
        "written": written,
        "acceptance_rate": round(accepted / written, 3) if written else None,
        "rejection_reasons": dict(reasons),
        "seconds_per_quiz": round(sum(r["seconds"] for r in runs) / len(runs), 1),
    }
    out_dir = Path(__file__).parent / "reports"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"{time.strftime('%Y%m%d-%H%M%S')}-quiz-{args.model.replace('/', '_')}.json"
    path.write_text(json.dumps({"summary": summary, "runs": runs}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Report: {path}")


if __name__ == "__main__":
    main()
