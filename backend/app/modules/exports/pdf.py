"""Builds printable PDFs of quizzes and study materials (multi-subject plan, phase 7).

Pure functions: data in, PDF bytes out. Nothing is stored; the PDF is sent straight to the
student who asked.

Safety:
- Every piece of text (written by the AI or taken from the student's document) is
  escaped before it goes into a ReportLab paragraph. ReportLab paragraphs understand a
  small markup language, including <img src=...>, which could read files from the server.
  Escaping turns any such markup into plain visible text.
- The student version of a quiz never contains answers or explanations; only the
  teacher version has the answer key (tested in test_exports.py).

Fonts: PDF's built-in fonts cannot show Turkish (ğ, ş, ı) or Cyrillic letters, so a TrueType
font with wide coverage is used when one is found: PDF_FONT_PATH if set, otherwise DejaVu
Sans (standard on Linux servers) or Arial (Windows). Without one, Helvetica is used and
letters it cannot show are simplified.
"""

import io
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.core.config import get_settings
from app.modules.study.grounding import check_citations

LETTERS = "ABCDEFGH"
INK = colors.HexColor("#1f2430")
MUTED = colors.HexColor("#5b6170")
PRIMARY = colors.HexColor("#2d45c9")
LINE = colors.HexColor("#c9ccd6")

_FONT_CANDIDATES = [
    (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    ("/usr/share/fonts/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
    ("C:/Windows/Fonts/DejaVuSans.ttf", "C:/Windows/Fonts/DejaVuSans-Bold.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/Library/Fonts/Arial Unicode.ttf", "/Library/Fonts/Arial Unicode.ttf"),
]


@dataclass(frozen=True)
class Fonts:
    regular: str
    bold: str
    unicode: bool  # False: Helvetica, which cannot show every letter


@lru_cache
def fonts() -> Fonts:
    custom = get_settings().pdf_font_path
    candidates = ([(custom, custom)] if custom else []) + _FONT_CANDIDATES
    for regular, bold in candidates:
        if Path(regular).is_file():
            try:
                pdfmetrics.registerFont(TTFont("MentoraSans", regular))
                bold_path = bold if Path(bold).is_file() else regular
                pdfmetrics.registerFont(TTFont("MentoraSans-Bold", bold_path))
                return Fonts("MentoraSans", "MentoraSans-Bold", True)
            except Exception:  # an unreadable font file: try the next one
                continue
    return Fonts("Helvetica", "Helvetica-Bold", False)


def clean(text: Any) -> str:
    """Text made safe for a ReportLab paragraph: markup escaped, control characters gone,
    and (only without a Unicode font) letters simplified to ones Helvetica can show."""
    s = str(text if text is not None else "")
    s = "".join(ch for ch in s if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    if not fonts().unicode:
        s = unicodedata.normalize("NFKD", s).replace("ı", "i")
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
        s = s.encode("cp1252", "replace").decode("cp1252")
    return escape(s).replace("\n", "<br/>")


def _styles() -> dict[str, ParagraphStyle]:
    f = fonts()
    base = ParagraphStyle("base", fontName=f.regular, fontSize=10.5, leading=15, textColor=INK)
    return {
        "body": base,
        "muted": ParagraphStyle("muted", parent=base, fontSize=9, leading=12, textColor=MUTED),
        "title": ParagraphStyle("title", parent=base, fontName=f.bold, fontSize=18, leading=23),
        "h2": ParagraphStyle(
            "h2",
            parent=base,
            fontName=f.bold,
            fontSize=13,
            leading=17,
            spaceBefore=8,
            spaceAfter=4,
            textColor=PRIMARY,
        ),
        "q": ParagraphStyle("q", parent=base, fontName=f.bold, alignment=TA_LEFT),
        "option": ParagraphStyle("option", parent=base, leftIndent=14),
        "bullet": ParagraphStyle("bullet", parent=base, leftIndent=12, bulletIndent=2),
    }


def _pages(pages: list[int]) -> str:
    if not pages:
        return ""
    label = "p." if len(pages) == 1 else "pp."
    return f"{label} {', '.join(str(p) for p in pages)}"


def _build(title: str, story: list[Any], subject: str) -> bytes:
    out = io.BytesIO()
    f = fonts()
    created = datetime.now(UTC).strftime("%d %b %Y")

    def footer(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setFont(f.regular, 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 10 * mm, f"Mentora · {created}")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"{doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        out,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title=title[:200],
        author="Mentora",
        subject=subject,
        creator="Mentora",
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return out.getvalue()


def _header(title: str, source: str, kind: str, s: dict[str, ParagraphStyle]) -> list[Any]:
    return [
        Paragraph(clean(kind), s["muted"]),
        Paragraph(clean(title), s["title"]),
        Paragraph(clean(f"From: {source}"), s["muted"]),
        Spacer(1, 6 * mm),
    ]


# ---------- quizzes ----------


@dataclass(frozen=True)
class QuizItem:
    question_type: str
    prompt: str
    answer_data: dict[str, Any]
    explanation: str
    source_pages: list[int]


def _correct(q: QuizItem) -> str:
    if q.question_type == "multiple_choice":
        i = q.answer_data["correct_index"]
        return f"{LETTERS[i]}) {q.answer_data['options'][i]}"
    if q.question_type == "true_false":
        return "True" if q.answer_data["value"] else "False"
    return " / ".join(q.answer_data["answers"])


def quiz_pdf(
    title: str, source: str, questions: list[QuizItem], *, teacher: bool, minutes: int = 0
) -> bytes:
    """Student version: questions only, with space to answer. Teacher version: the same
    questions followed by the answer key with explanations and pages."""
    s = _styles()
    story = _header(title, source, "Quiz · teacher version" if teacher else "Quiz", s)
    if not teacher:
        line = "Name: ______________________________    Date: ______________"
        story.append(Paragraph(clean(line), s["body"]))
        info = f"{len(questions)} questions" + (f" · {minutes} minutes" if minutes else "")
        story += [Paragraph(clean(info), s["muted"]), Spacer(1, 5 * mm)]
    for n, q in enumerate(questions, start=1):
        block: list[Any] = [Paragraph(f"{n}. {clean(q.prompt)}", s["q"]), Spacer(1, 2 * mm)]
        if q.question_type == "multiple_choice":
            for i, option in enumerate(q.answer_data["options"]):
                block.append(
                    Paragraph(
                        f"○ {LETTERS[i]})  {clean(option)}"
                        if fonts().unicode
                        else f"[ ] {LETTERS[i]})  {clean(option)}",
                        s["option"],
                    )
                )
        elif q.question_type == "true_false":
            block.append(Paragraph(clean("True  /  False"), s["option"]))
        else:
            block.append(Paragraph(clean("Answer: ________________________"), s["option"]))
        block.append(Spacer(1, 5 * mm))
        story.append(KeepTogether(block))

    if teacher:
        story += [PageBreak(), Paragraph(clean("Answer key"), s["h2"])]
        for n, q in enumerate(questions, start=1):
            story.append(
                KeepTogether(
                    [
                        Paragraph(f"{n}. {clean(_correct(q))}", s["q"]),
                        Paragraph(clean(check_citations(q.explanation, set()).text), s["body"]),
                        Paragraph(
                            clean(f"From your document: {_pages(q.source_pages)}"), s["muted"]
                        ),
                        Spacer(1, 4 * mm),
                    ]
                )
            )
    return _build(title, story, "Quiz")


# ---------- study materials ----------


def material_pdf(title: str, source: str, kind: str, content: dict[str, Any]) -> bytes:
    s = _styles()
    names = {"summary": "Summary", "guide": "Study guide", "flashcards": "Flashcards"}
    story = _header(title, source, names.get(kind, "Study material"), s)

    def cite(pages: list[int]) -> str:
        p = _pages(pages)
        return f'  <font color="#5b6170" size="8.5">({clean(p)})</font>' if p else ""

    if kind == "summary":
        for section in content.get("sections", []):
            story.append(Paragraph(clean(section["heading"]), s["h2"]))
            for point in section["points"]:
                story.append(
                    Paragraph(
                        clean(point["text"]) + cite(point["pages"]), s["bullet"], bulletText="•"
                    )
                )
    elif kind == "guide":
        story += [
            Paragraph(clean("Overview"), s["h2"]),
            Paragraph(clean(content["overview"]), s["body"]),
        ]
        if content.get("key_terms"):
            story.append(Paragraph(clean("Key terms"), s["h2"]))
            rows = [
                [
                    Paragraph(f"<b>{clean(t['term'])}</b>", s["body"]),
                    Paragraph(clean(t["definition"]) + cite(t["pages"]), s["body"]),
                ]
                for t in content["key_terms"]
            ]
            table = Table(rows, colWidths=[45 * mm, None])
            table.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            story.append(table)
        for section in content.get("sections", []):
            story += [
                Paragraph(clean(section["heading"]), s["h2"]),
                Paragraph(clean(section["explanation"]) + cite(section["pages"]), s["body"]),
            ]
        checks = content.get("self_check", [])
        if checks:
            story.append(Paragraph(clean("Check yourself"), s["h2"]))
            for n, c in enumerate(checks, start=1):
                story += [Paragraph(f"{n}. {clean(c['question'])}", s["body"]), Spacer(1, 6 * mm)]
            # Answers on their own page, so students can test themselves first.
            story += [PageBreak(), Paragraph(clean("Check yourself: answers"), s["h2"])]
            for n, c in enumerate(checks, start=1):
                story.append(Paragraph(f"{n}. {clean(c['answer'])}" + cite(c["pages"]), s["body"]))
    else:  # flashcards: a two-column sheet (fold down the middle to self-test)
        rows = [[Paragraph("<b>Front</b>", s["muted"]), Paragraph("<b>Back</b>", s["muted"])]]
        rows += [
            [
                Paragraph(clean(c["front"]), s["q"]),
                Paragraph(clean(c["back"]) + cite(c["pages"]), s["body"]),
            ]
            for c in content.get("cards", [])
        ]
        table = Table(rows, colWidths=["45%", "55%"], repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                    ("LINEAFTER", (0, 0), (0, -1), 1, MUTED),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.append(table)
    return _build(title, story, names.get(kind, "Study material"))
