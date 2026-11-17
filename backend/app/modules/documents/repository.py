"""Database queries for documents. Every query that reads one document filters by owner."""

import uuid

from sqlalchemy import Row, func, select, text
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


# Matches are marked with these in snippets; the page turns them into highlights.
SNIPPET_OPTIONS = (
    "StartSel=\u27e6, StopSel=\u27e7, MaxWords=40, MinWords=15, "
    'MaxFragments=2, FragmentDelimiter=" \u2026 "'
)

_SEARCH = text(
    """
    WITH q AS (SELECT to_tsquery('mentora_text', :tsquery) AS query),
    best AS (
        SELECT c.id, ts_rank_cd(c.search, q.query) AS rank
        FROM document_chunks c, q
        WHERE c.owner_id = :owner_id
          AND c.search @@ q.query
          AND (CAST(:document_id AS uuid) IS NULL OR c.document_id = CAST(:document_id AS uuid))
        ORDER BY rank DESC, c.page_start
        LIMIT :limit
    )
    SELECT c.document_id, d.title, c.page_start, c.page_end, c.heading,
           ts_headline('mentora_text', c.text, q.query, :options) AS snippet
    FROM best
    JOIN document_chunks c ON c.id = best.id
    JOIN documents d ON d.id = c.document_id AND d.owner_id = :owner_id
    CROSS JOIN q
    ORDER BY best.rank DESC, c.page_start
    """
)


async def search_chunks(
    db: AsyncSession,
    owner_id: uuid.UUID,
    tsquery: str,
    document_id: uuid.UUID | None,
    limit: int,
) -> list[Row]:
    """Only this owner's chunks (filtered on the chunk and on its document). `tsquery` is
    built by the service from letters and digits only, and is passed as a parameter."""
    result = await db.execute(
        _SEARCH,
        {
            "tsquery": tsquery,
            "owner_id": owner_id,
            "document_id": document_id,
            "limit": limit,
            "options": SNIPPET_OPTIONS,
        },
    )
    return list(result.all())
