"""Database queries for documents. Every query that reads one document filters by owner."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.documents.models import Document


async def owned(db: AsyncSession, owner_id: uuid.UUID, document_id: uuid.UUID) -> Document | None:
    """The document only if this owner has it; otherwise None (whether it exists or not)."""
    return await db.scalar(
        select(Document).where(Document.id == document_id, Document.owner_id == owner_id)
    )


async def list_owned(db: AsyncSession, owner_id: uuid.UUID) -> list[Document]:
    rows = await db.scalars(
        select(Document)
        .where(Document.owner_id == owner_id)
        .order_by(Document.created_at.desc(), Document.id)
    )
    return list(rows)


async def usage(db: AsyncSession, owner_id: uuid.UUID) -> tuple[int, int]:
    """(number of documents, total bytes) for one owner."""
    count, total = (
        await db.execute(
            select(func.count(Document.id), func.coalesce(func.sum(Document.size_bytes), 0)).where(
                Document.owner_id == owner_id
            )
        )
    ).one()
    return int(count), int(total)


async def by_hash(db: AsyncSession, owner_id: uuid.UUID, sha256: str) -> Document | None:
    return await db.scalar(
        select(Document).where(Document.owner_id == owner_id, Document.sha256 == sha256)
    )
