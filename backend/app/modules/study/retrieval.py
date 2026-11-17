"""Chooses which parts of a document the teacher sees for one question.

In order:
1. Pages the student names ("explain page 4", "pages 2-3") are always included.
2. A short document (under WHOLE_DOCUMENT_TOKENS) is sent whole: nothing can be missed.
3. Otherwise the pages of the best-matching chunks by full-text search (any of the question's words,
   ranked), topped up with the pages the teacher used for the previous answer, so
   follow-ups like "explain that again" keep their context.

Everything is filtered by owner and document. The model only ever receives text from the
student's own document, labelled with its pages.
"""

import re
from dataclasses import dataclass, field

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.documents.models import Document, DocumentChunk, DocumentPage
from app.modules.documents.service import search_terms

WHOLE_DOCUMENT_TOKENS = 6000
MAX_CONTEXT_TOKENS = 6000
TOP_CHUNKS = 6
MAX_NAMED_PAGES = 3

# Words that say nothing about the content; dropped before ranking.
_STOP = frozenset(
    """a an and are as at be by can could do does explain for from give how i in is it
    me my of on or please show tell that the this to was what when where which who why
    will with you your about page pages document pdf bir bu ve ile ne nedir nasıl için
    mi mı da de""".split()
)

_PAGE_REF = re.compile(
    r"\b(?:pages?|p\.|pp\.|sayfa)\s*(\d{1,4})(?:\s*(?:-|–|to|and)\s*(\d{1,4}))?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Excerpt:
    page_start: int
    page_end: int
    heading: str | None
    text: str

    @property
    def label(self) -> str:
        if self.page_start == self.page_end:
            return f"[p. {self.page_start}]"
        return f"[pp. {self.page_start}–{self.page_end}]"


@dataclass
class Context:
    excerpts: list[Excerpt] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # e.g. "page 9 has no readable text"
    whole_document: bool = False

    @property
    def pages(self) -> set[int]:
        """Every page the teacher was given: the only pages it may cite."""
        return {p for e in self.excerpts for p in range(e.page_start, e.page_end + 1)}


def named_pages(question: str, page_count: int) -> tuple[list[int], list[int]]:
    """Pages named in the question: (pages that exist, pages that do not)."""
    found: list[int] = []
    for m in _PAGE_REF.finditer(question):
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else start
        if end < start or end - start > 10:
            end = start
        found.extend(range(start, end + 1))
    found = list(dict.fromkeys(found))
    valid = [p for p in found if 1 <= p <= page_count][:MAX_NAMED_PAGES]
    missing = [p for p in found if not 1 <= p <= page_count]
    return valid, missing


def ranking_terms(question: str) -> list[str]:
    return [t for t in search_terms(question) if t not in _STOP]


def _tokens(chunk_text: str) -> int:
    return round(len(chunk_text.split()) * 1.35)


_RANKED = text(
    """
    SELECT c.id
    FROM document_chunks c
    WHERE c.owner_id = :owner_id AND c.document_id = :document_id
      AND c.search @@ to_tsquery('mentora_text', :tsquery)
    ORDER BY ts_rank_cd(c.search, to_tsquery('mentora_text', :tsquery)) DESC, c.position
    LIMIT :limit
    """
)


async def build_context(
    db: AsyncSession, doc: Document, question: str, previous_pages: list[int]
) -> Context:
    """Excerpts are whole pages, each labelled with its own page number, so every
    citation the teacher writes can be exact. Chunks are only used to find the pages."""
    ctx = Context()
    owner = doc.owner_id
    chunks = list(
        await db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == doc.id, DocumentChunk.owner_id == owner)
            .order_by(DocumentChunk.position)
        )
    )
    page_count = doc.page_count or 0

    # 1. Pages the student named: always included.
    named, missing = named_pages(question, page_count)
    if missing:
        ctx.notes.append(
            f"The student mentioned page {', '.join(map(str, missing))}, but the document "
            f"has only {page_count} pages."
        )

    # 2. A short document goes whole; 3. otherwise the best matches, then the pages the
    # previous answer used (for follow-up questions).
    wanted: list[int] = []
    if sum(c.token_count for c in chunks) <= WHOLE_DOCUMENT_TOKENS:
        ctx.whole_document = True
        wanted = list(range(1, page_count + 1))
    else:
        terms = ranking_terms(question)
        if terms:
            ids = list(
                await db.scalars(
                    _RANKED,
                    {
                        "owner_id": owner,
                        "document_id": doc.id,
                        "tsquery": " | ".join(f"{t}:*" for t in terms),
                        "limit": TOP_CHUNKS,
                    },
                )
            )
            by_id = {c.id: c for c in chunks}
            for i in ids:
                c = by_id.get(i)
                if c is not None:
                    wanted.extend(range(c.page_start, c.page_end + 1))
        wanted.extend(previous_pages)

    order = list(dict.fromkeys([*named, *wanted]))
    if not order:
        return ctx
    pages = {
        p.page_number: p
        for p in await db.scalars(
            select(DocumentPage).where(
                DocumentPage.document_id == doc.id, DocumentPage.page_number.in_(order)
            )
        )
    }
    headings: dict[int, str] = {}
    for c in chunks:
        if c.heading:
            headings.setdefault(c.page_start, c.heading)

    used = 0
    for number in order:
        page = pages.get(number)
        if page is None:
            continue
        if not page.has_text:
            if number in named:
                ctx.notes.append(
                    f"Page {number} has no readable text (it looks like a scanned image), "
                    "so you cannot see its content."
                )
            continue
        cost = _tokens(page.text)
        if number not in named and ctx.excerpts and used + cost > MAX_CONTEXT_TOKENS:
            continue
        ctx.excerpts.append(Excerpt(number, number, headings.get(number), page.text))
        used += cost
    ctx.excerpts.sort(key=lambda e: e.page_start)
    return ctx
