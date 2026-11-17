"""Phase 3: reading the text out of an uploaded PDF and splitting it into searchable chunks.

Runs in the background job worker, never during the upload request.

    stored PDF -> text of every page (our own code, pypdf, no AI) -> chunks with page
    numbers -> PostgreSQL full-text index -> document status "ready"

Pages without a text layer (scans, photos of pages) are kept as pages with has_text=False.
Reading those needs OCR, which is planned with an AI model once a provider is chosen.

Extraction and chunking are pure functions (tested without a database); `run_job` is the
part that touches storage and the database.
"""

import io
import logging
import re
import time
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi.concurrency import run_in_threadpool
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.storage import Storage
from app.modules.documents.models import Document, DocumentChunk, DocumentPage

logger = logging.getLogger(__name__)

JOB_KIND = "process_document"

MIN_TEXT_CHARS = 25  # fewer letters and digits than this: a scan, or only a page number
MAX_PAGE_CHARS = 30_000  # more than any real page; protects the database from odd files
TARGET_WORDS = 350  # about 470 tokens: small enough to cite a page, big enough for context
MAX_WORDS = 500
MIN_WORDS_BEFORE_HEADING_BREAK = 60
TOKENS_PER_WORD = 1.35  # rough estimate, for budgeting only

# Search snippets mark matches with these, so they are removed from document text.
MARK_START, MARK_END = "⟦", "⟧"


class ProcessingTimeout(Exception):
    pass


class UnreadablePdf(Exception):
    pass


@dataclass(frozen=True)
class PageText:
    number: int  # 1 = the first page
    text: str
    has_text: bool


@dataclass(frozen=True)
class Chunk:
    position: int
    page_start: int
    page_end: int
    heading: str | None
    text: str

    @property
    def token_count(self) -> int:
        return max(1, round(len(self.text.split()) * TOKENS_PER_WORD))


# ---------- reading the text ----------


def clean_text(raw: str) -> str:
    """Make extracted text safe to store and pleasant to search."""
    # PostgreSQL text cannot hold NUL; other control characters are noise from fonts.
    text = "".join(
        ch if ch in "\n\t" or unicodedata.category(ch)[0] != "C" else " "
        for ch in unicodedata.normalize("NFC", raw)
    )
    text = text.replace(MARK_START, "").replace(MARK_END, "").replace("­", "")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # words split across lines: "data-\nbase"
    text = re.sub(r"[ \t ]+", " ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:MAX_PAGE_CHARS]


def _has_text(text: str) -> bool:
    return sum(ch.isalnum() for ch in text) >= MIN_TEXT_CHARS


def extract_pages(data: bytes, *, time_limit_s: float) -> list[PageText]:
    """The text of every page. A page that cannot be read counts as a page without text;
    a file that cannot be opened at all raises UnreadablePdf."""
    started = time.monotonic()
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise UnreadablePdf("encrypted")
        pages = list(reader.pages)
    except UnreadablePdf:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError, OSError, RecursionError) as exc:
        raise UnreadablePdf(type(exc).__name__) from exc

    out: list[PageText] = []
    for number, page in enumerate(pages, start=1):
        if time.monotonic() - started > time_limit_s:
            raise ProcessingTimeout(f"stopped at page {number}")
        try:
            text = clean_text(page.extract_text() or "")
        except Exception:  # one damaged page must not lose the rest of the document
            logger.warning("Could not read the text of page %s", number)
            text = ""
        out.append(PageText(number=number, text=text, has_text=_has_text(text)))
    return out


# ---------- splitting into chunks ----------

_NUMBERED = re.compile(r"^(\d+(\.\d+)*\.?|[IVX]+\.|[A-Z]\.)\s+\S")
_KEYWORD = re.compile(
    r"^(chapter|section|unit|lecture|week|part|module|topic|appendix|summary|introduction|"
    r"conclusion|bölüm|ünite|глава|раздел)\b",
    re.IGNORECASE,
)


def looks_like_heading(line: str) -> bool:
    """A cheap guess from the text alone (pypdf gives no font sizes): short, no sentence
    ending, and either numbered, a known keyword, ALL CAPS or Title Case."""
    words = line.split()
    if not (1 <= len(words) <= 10) or not (3 <= len(line) <= 90):
        return False
    if line[-1] in ".,;:!?" or not (line[0].isupper() or line[0].isdigit()):
        return False
    if _NUMBERED.match(line) or _KEYWORD.match(line):
        return True
    letters = [ch for ch in line if ch.isalpha()]
    if len(letters) >= 4 and all(ch.isupper() for ch in letters):
        return True
    significant = [w for w in words if len(w) > 3]
    return len(words) >= 2 and bool(significant) and all(w[0].isupper() for w in significant)


def _blocks(pages: list[PageText]):
    """(page number, heading or None, paragraph text) in reading order."""
    for page in pages:
        if not page.has_text:
            continue
        para: list[str] = []
        for line in page.text.split("\n"):
            if not line:
                if para:
                    yield page.number, None, " ".join(para)
                    para = []
                continue
            if looks_like_heading(line):
                if para:
                    yield page.number, None, " ".join(para)
                    para = []
                yield page.number, line, ""
                continue
            para.append(line)
        if para:
            yield page.number, None, " ".join(para)


def _pieces(text: str) -> list[str]:
    """A paragraph longer than MAX_WORDS, cut into MAX_WORDS-sized pieces."""
    words = text.split()
    return [" ".join(words[i : i + MAX_WORDS]) for i in range(0, len(words), MAX_WORDS)]


def make_chunks(pages: list[PageText]) -> list[Chunk]:
    """Group paragraphs into chunks of about TARGET_WORDS words. A new heading starts a new
    chunk (once the current one has some substance). Chunks may run onto the next page;
    page_start and page_end then show both."""
    chunks: list[Chunk] = []
    parts: list[str] = []
    words = 0
    start = end = 0
    heading: str | None = None  # the most recent heading seen
    chunk_heading: str | None = None

    def flush() -> None:
        nonlocal parts, words
        if parts:
            text = "\n\n".join(parts)
            chunks.append(Chunk(len(chunks), start, end, chunk_heading, text))
        parts, words = [], 0

    for page, head, text in _blocks(pages):
        if head is not None:
            if words >= MIN_WORDS_BEFORE_HEADING_BREAK:
                flush()
            heading = head[:300]
            if parts:
                parts.append(head)  # keep it in the text when it does not start a chunk
                words += len(head.split())
            continue
        for piece in _pieces(text):
            n = len(piece.split())
            if parts and words + n > TARGET_WORDS:
                flush()
            if not parts:
                start, chunk_heading = page, heading
            parts.append(piece)
            words += n
            end = page
    flush()
    return chunks


# ---------- the background job ----------


async def run_job(db: AsyncSession, storage: Storage, payload: dict[str, Any]) -> None:
    await process_document(db, storage, uuid.UUID(payload["document_id"]))


async def process_document(db: AsyncSession, storage: Storage, document_id: uuid.UUID) -> None:
    """Read, chunk and index one document. Safe to run again: old pages and chunks are
    replaced. Storage errors raise (the job is retried); a bad file is recorded as failed."""
    doc = await db.get(Document, document_id)
    if doc is None:
        return  # deleted while waiting: nothing to do
    data = await run_in_threadpool(storage.read, doc.storage_key)  # StorageError: retried

    try:
        pages = await run_in_threadpool(
            extract_pages, data, time_limit_s=get_settings().document_processing_seconds
        )
    except UnreadablePdf:
        await _finish(db, doc, status="failed", error_code="pdf_unreadable")
        return
    except ProcessingTimeout:
        await _finish(db, doc, status="failed", error_code="processing_timeout")
        return
    chunks = make_chunks(pages)

    await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))
    await db.execute(delete(DocumentPage).where(DocumentPage.document_id == doc.id))
    db.add_all(
        DocumentPage(document_id=doc.id, page_number=p.number, text=p.text, has_text=p.has_text)
        for p in pages
    )
    db.add_all(
        DocumentChunk(
            document_id=doc.id,
            owner_id=doc.owner_id,
            position=c.position,
            page_start=c.page_start,
            page_end=c.page_end,
            heading=c.heading,
            text=c.text,
            token_count=c.token_count,
        )
        for c in chunks
    )
    with_text = sum(p.has_text for p in pages)
    doc.page_count = len(pages) or doc.page_count
    await _finish(
        db,
        doc,
        status="ready",
        error_code=None if with_text else "no_text_layer",
        pages_with_text=with_text,
    )
    logger.info(
        "Document %s processed: %s pages, %s with text, %s chunks",
        doc.id,
        len(pages),
        with_text,
        len(chunks),
    )


async def _finish(
    db: AsyncSession,
    doc: Document,
    *,
    status: str,
    error_code: str | None,
    pages_with_text: int | None = None,
) -> None:
    doc.status = status
    doc.error_code = error_code
    doc.pages_with_text = pages_with_text
    doc.processed_at = datetime.now(UTC)
    await db.commit()


async def give_up(db: AsyncSession, payload: dict[str, Any]) -> None:
    """Every attempt failed (for example storage was down each time)."""
    doc = await db.get(Document, uuid.UUID(payload["document_id"]))
    if doc is not None and doc.status == "processing":
        await _finish(db, doc, status="failed", error_code="processing_failed")
