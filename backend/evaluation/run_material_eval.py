"""Study material evaluation (multi-subject plan, phase 6 gate).

    cd backend
    python -m evaluation.run_material_eval --pause 4

Writes a summary, a study guide and flashcards from the made-up sample document in
run_grounding_eval.py (never a student upload, so it is safe on a free plan) and checks
each with the same code the app uses. Writes evaluation/reports/<timestamp>-materials-*.json.

Metrics per kind: passed the checks (yes/no), items kept versus written (items citing
pages that were not sent, duplicates and give-aways are dropped), and time taken.
"""

import argparse
import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.ai.base import AIProvider, StructuredRequest
from app.ai.factory import build_provider
from app.core.config import get_settings
from app.modules.materials.generation import (
    MAX_TOKENS,
    SCHEMAS,
    SYSTEM,
    build_prompt,
    check_content,
)
from evaluation.run_grounding_eval import PAGES, TITLE


@dataclass(frozen=True)
class _Page:
    page_number: int
    text: str


def _count(kind: str, data: Any) -> int:
    if not isinstance(data, dict):
        return 0
    if kind == "summary":
        return sum(
            len(s.get("points", [])) for s in data.get("sections", []) if isinstance(s, dict)
        )
    if kind == "guide":
        return len(data.get("key_terms", [])) + len(data.get("sections", []))
    return len(data.get("cards", []))


async def one(provider: AIProvider, kind: str) -> dict:
    settings = {"card_count": 12}
    pages = [_Page(n, t) for n, t in PAGES.items()]
    request = StructuredRequest(
        system=SYSTEM,
        prompt=build_prompt(kind, TITLE, pages, settings),
        schema=SCHEMAS[kind],
        max_tokens=MAX_TOKENS.get(kind) or 120 * 12 + 1500,
    )
    started = time.monotonic()
    result = await provider.generate_structured(request)
    content = check_content(kind, result.data, set(PAGES), settings)
    return {
        "kind": kind,
        "passed": content is not None,
        "written": _count(kind, result.data),
        "kept": _count(kind, content),
        "seconds": round(time.monotonic() - started, 1),
        "content": content,
    }


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--model", default=settings.ai_model)
    parser.add_argument("--pause", type=float, default=0.0)
    args = parser.parse_args()
    provider = build_provider(settings, model=args.model)
    if provider is None:
        raise SystemExit("No AI provider configured (AI_PROVIDER in backend/.env).")

    async def run_all() -> list[dict]:
        out = []
        for i, kind in enumerate(["summary", "guide", "flashcards"]):
            if i and args.pause:
                await asyncio.sleep(args.pause)
            r = await one(provider, kind)
            print(
                f"{kind:10} passed={r['passed']} kept {r['kept']}/{r['written']} "
                f"in {r['seconds']} s"
            )
            out.append(r)
        return out

    results = asyncio.run(run_all())
    out_dir = Path(__file__).parent / "reports"
    out_dir.mkdir(exist_ok=True)
    path = (
        out_dir / f"{time.strftime('%Y%m%d-%H%M%S')}-materials-{args.model.replace('/', '_')}.json"
    )
    path.write_text(
        json.dumps({"model": args.model, "results": results}, indent=2), encoding="utf-8"
    )
    print(f"Report: {path}")


if __name__ == "__main__":
    main()
