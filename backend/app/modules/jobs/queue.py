"""Adding, claiming and finishing background jobs."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.jobs.models import Job

# A job still "running" after this long belonged to a worker that stopped; it is retried.
STALE_AFTER = timedelta(minutes=15)


def now() -> datetime:
    return datetime.now(UTC)


def enqueue(
    db: AsyncSession, kind: str, payload: dict[str, Any], *, user_id: uuid.UUID | None = None
) -> Job:
    """Add a job to the session. It is saved by the caller's commit, so the job and the
    change that needs it are stored together or not at all."""
    job = Job(kind=kind, payload=payload, user_id=user_id, status="queued", run_after=now())
    db.add(job)
    return job


async def claim(db: AsyncSession) -> Job | None:
    """Take the oldest job that is due and mark it running. Commits."""
    t = now()
    job = await db.scalar(
        select(Job)
        .where(
            or_(
                and_(Job.status == "queued", Job.run_after <= t),
                and_(Job.status == "running", Job.locked_at < t - STALE_AFTER),
            )
        )
        .order_by(Job.run_after, Job.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job is None:
        await db.rollback()
        return None
    job.status = "running"
    job.locked_at = t
    job.attempts += 1
    await db.commit()
    return job


async def mark_done(db: AsyncSession, job_id: uuid.UUID) -> None:
    job = await db.get(Job, job_id)
    if job is not None:
        job.status, job.finished_at, job.error, job.locked_at = "done", now(), None, None
        await db.commit()


async def mark_failed(db: AsyncSession, job_id: uuid.UUID, error: str) -> bool:
    """Record a failure. Returns True if the job will be tried again later."""
    job = await db.get(Job, job_id)
    if job is None:
        return False
    job.error = error[:300]
    job.locked_at = None
    retry = job.attempts < job.max_attempts
    if retry:
        job.status = "queued"
        job.run_after = now() + timedelta(seconds=30 * 2 ** (job.attempts - 1))
    else:
        job.status, job.finished_at = "failed", now()
    await db.commit()
    return retry
