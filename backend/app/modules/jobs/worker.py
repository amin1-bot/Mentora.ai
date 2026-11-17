"""Runs background jobs.

Two ways to run it:
- Inside the API (the default for local development, JOB_WORKER_IN_API=true): it starts
  with the server, so there is nothing else to run.
- As its own process (production; several can run at once):
      python -m app.modules.jobs.worker

Handlers are registered by kind. A handler raises for errors worth retrying (storage or
database briefly unavailable). Problems with the input itself it records and returns.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.core.storage import Storage, get_storage
from app.modules.jobs import queue

logger = logging.getLogger(__name__)

Run = Callable[[AsyncSession, Storage, dict[str, Any]], Awaitable[None]]
GiveUp = Callable[[AsyncSession, dict[str, Any]], Awaitable[None]]


@dataclass(frozen=True)
class Handler:
    run: Run
    give_up: GiveUp  # called once, when every attempt has failed


def handlers() -> dict[str, Handler]:
    from app.modules.documents import processing

    return {processing.JOB_KIND: Handler(processing.run_job, processing.give_up)}


async def run_once(storage: Storage) -> bool:
    """Run one due job, if there is one. Returns False when there was nothing to do."""
    async with SessionLocal() as db:
        job = await queue.claim(db)
        if job is None:
            return False
        job_id, kind, payload = job.id, job.kind, dict(job.payload)

    handler = handlers().get(kind)
    async with SessionLocal() as db:
        if handler is None:
            logger.error("Job %s has unknown kind %s", job_id, kind)
            await queue.mark_failed(db, job_id, f"unknown kind {kind}")
            return True
        try:
            await handler.run(db, storage, payload)
        except Exception as exc:  # any failure is recorded and retried later
            await db.rollback()
            logger.exception("Job %s (%s) failed", job_id, kind)
            if not await queue.mark_failed(db, job_id, type(exc).__name__):
                await handler.give_up(db, payload)
            return True
        await queue.mark_done(db, job_id)
    return True


async def run_until_idle(storage: Storage, limit: int = 100) -> int:
    """Run due jobs until none is left (tests and scripts). Returns how many ran."""
    ran = 0
    while ran < limit and await run_once(storage):
        ran += 1
    return ran


async def run_forever(storage: Storage, stop: asyncio.Event, poll_seconds: float = 2.0) -> None:
    logger.info("Job worker started")
    errors = 0
    while not stop.is_set():
        try:
            busy = await run_once(storage)
            errors = 0
        except Exception as exc:  # e.g. the database is restarting: wait and keep going
            errors += 1
            # Full details once; after that one line, waiting longer each time (max 1 min).
            logger.warning(
                "Job worker cannot reach the database: %s", type(exc).__name__, exc_info=errors == 1
            )
            busy = False
        if not busy:
            wait = min(poll_seconds * 2**errors, 60.0) if errors else poll_seconds
            try:
                await asyncio.wait_for(stop.wait(), timeout=wait)
            except TimeoutError:
                pass
    logger.info("Job worker stopped")


def _main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        asyncio.run(run_forever(get_storage(), asyncio.Event()))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    _main()
