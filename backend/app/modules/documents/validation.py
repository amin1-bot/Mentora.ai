"""Checks an uploaded file before anything is stored. Pure code, no database.

What is checked, in order:
1. Name: must end in .pdf (the browser's content type is ignored: it is easy to fake).
2. Size: not empty, not over the limit.
3. Content: must really be a PDF (starts with the %PDF- signature), and pypdf must be able
   to open it. The file is only *read*; nothing inside it is ever run.
4. Encryption: password-protected PDFs are refused (they could not be studied later).
5. Pages: at least one, at most the limit.
6. Active content: PDFs with JavaScript, launch actions or embedded files are refused.
   Lecture notes do not need them, and refusing them removes a common attack route.
   This is a byte scan, a first line of defence, not a virus scanner (planned before
   uploads are opened to minors).
"""

import hashlib
import io
import re
import unicodedata
from dataclasses import dataclass

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.core.errors import PayloadTooLarge, Unprocessable, UnsupportedMediaType

PDF_MIME = "application/pdf"
_ACTIVE_CONTENT = (b"/JavaScript", b"/JS ", b"/JS(", b"/JS<", b"/Launch", b"/EmbeddedFile")


@dataclass(frozen=True)
class CheckedPdf:
    filename: str  # cleaned, safe to show
    title: str  # filename without .pdf, the starting title
    size_bytes: int
    page_count: int
    sha256: str


def clean_filename(raw: str | None) -> str:
    """Keep only the last path part, drop control characters, limit the length."""
    name = re.split(r"[\\/]", raw or "")[-1]
    name = "".join(
        ch for ch in unicodedata.normalize("NFC", name) if unicodedata.category(ch)[0] != "C"
    )
    name = re.sub(r"\s+", " ", name).strip(" .")
    if len(name) > 150:
        stem, dot, ext = name.rpartition(".")
        name = (stem[: 150 - len(ext) - 1] + dot + ext) if dot else name[:150]
    return name or "document.pdf"


def check_pdf(
    data: bytes, raw_filename: str | None, *, max_bytes: int, max_pages: int
) -> CheckedPdf:
    filename = clean_filename(raw_filename)
    if not filename.lower().endswith(".pdf"):
        raise UnsupportedMediaType("Only PDF files can be uploaded for now.", code="not_a_pdf")
    if not data:
        raise Unprocessable("That file is empty.", code="empty_file")
    if len(data) > max_bytes:
        raise PayloadTooLarge(
            f"That file is larger than {max_bytes // (1024 * 1024)} MB.", code="file_too_large"
        )
    if b"%PDF-" not in data[:1024]:
        raise UnsupportedMediaType(
            "That file is not a real PDF, even though its name ends in .pdf.", code="not_a_pdf"
        )
    if any(marker in data for marker in _ACTIVE_CONTENT):
        raise Unprocessable(
            "This PDF contains scripts or embedded files, which Mentora does not accept. "
            "Try exporting or printing it to a new PDF first.",
            code="pdf_active_content",
        )
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise Unprocessable(
                "This PDF is password-protected. Remove the password and upload it again.",
                code="pdf_encrypted",
            )
        pages = len(reader.pages)
    except Unprocessable:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError, OSError, RecursionError) as exc:
        raise Unprocessable(
            "That PDF is damaged and cannot be opened.", code="pdf_unreadable"
        ) from exc
    if pages < 1:
        raise Unprocessable("That PDF has no pages.", code="pdf_unreadable")
    if pages > max_pages:
        raise Unprocessable(
            f"That PDF has {pages} pages; the limit is {max_pages}.", code="too_many_pages"
        )
    return CheckedPdf(
        filename=filename,
        title=filename[:-4].strip() or "Untitled document",
        size_bytes=len(data),
        page_count=pages,
        sha256=hashlib.sha256(data).hexdigest(),
    )
