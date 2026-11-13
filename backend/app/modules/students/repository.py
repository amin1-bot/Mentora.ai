"""All database queries for student profiles and guardians."""

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.students.models import GuardianInvite, GuardianLink, StudentProfile


async def get_profile(session: AsyncSession, user_id: uuid.UUID) -> StudentProfile | None:
    return await session.get(StudentProfile, user_id)


async def get_link(
    session: AsyncSession, student_id: uuid.UUID, guardian_id: uuid.UUID
) -> GuardianLink | None:
    return await session.scalar(
        select(GuardianLink).where(
            GuardianLink.student_id == student_id, GuardianLink.guardian_id == guardian_id
        )
    )


async def has_approved_guardian(session: AsyncSession, student_id: uuid.UUID) -> bool:
    found = await session.scalar(
        select(GuardianLink.id)
        .where(GuardianLink.student_id == student_id, GuardianLink.status == "approved")
        .limit(1)
    )
    return found is not None


async def get_invite_by_token_hash(
    session: AsyncSession, token_hash: str
) -> GuardianInvite | None:
    return await session.scalar(
        select(GuardianInvite).where(GuardianInvite.token_hash == token_hash)
    )


async def cancel_open_invites(
    session: AsyncSession, student_id: uuid.UUID, now: datetime
) -> None:
    await session.execute(
        update(GuardianInvite)
        .where(
            GuardianInvite.student_id == student_id,
            GuardianInvite.accepted_at.is_(None),
            GuardianInvite.cancelled_at.is_(None),
        )
        .values(cancelled_at=now)
    )
