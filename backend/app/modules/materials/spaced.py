"""Spaced repetition for flashcards: a small version of the SM-2 schedule.

After each review the student rates the card: again, hard, good or easy. Cards they know
come back after longer and longer gaps; cards they miss come back soon. Pure functions,
so the schedule is easy to test and to change.
"""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Literal

Rating = Literal["again", "hard", "good", "easy"]

MIN_EASE = 1.3
MAX_INTERVAL_DAYS = 365
AGAIN_DELAY = timedelta(minutes=10)


@dataclass(frozen=True)
class CardState:
    reps: int = 0  # successful reviews in a row
    lapses: int = 0  # times forgotten
    ease: float = 2.5
    interval_days: float = 0.0


def schedule(state: CardState, rating: Rating, now: datetime) -> tuple[CardState, datetime]:
    """The card's new state and when it is due next."""
    if rating == "again":
        new = replace(
            state,
            reps=0,
            lapses=state.lapses + 1,
            ease=max(MIN_EASE, state.ease - 0.2),
            interval_days=0.0,
        )
        return new, now + AGAIN_DELAY

    if rating == "hard":
        interval = 1.0 if state.reps == 0 else max(1.0, state.interval_days * 1.2)
        ease = max(MIN_EASE, state.ease - 0.15)
    elif rating == "good":
        interval = (1.0, 3.0)[state.reps] if state.reps < 2 else state.interval_days * state.ease
        ease = state.ease
    else:  # easy
        interval = 4.0 if state.reps == 0 else state.interval_days * state.ease * 1.3
        ease = state.ease + 0.15
    interval = min(MAX_INTERVAL_DAYS, round(interval, 2))
    new = CardState(reps=state.reps + 1, lapses=state.lapses, ease=ease, interval_days=interval)
    return new, now + timedelta(days=interval)
