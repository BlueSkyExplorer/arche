"""Best-effort mapping of a school-format DOCX into a template-profile draft.

Deterministic, no LLM. Every field of the strict ``TemplateProfileCreate``
schema is populated; formatting defaults are explicitly separated from source
evidence so absent or low-confidence document metadata is never invented.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Length

from app.schemas.template_profile import AnswerSheetLayoutConfig, TemplateProfileImportDraft

A4_WIDTH_MM = 210.0
A4_HEIGHT_MM = 297.0
LETTER_WIDTH_MM = 215.9
LETTER_HEIGHT_MM = 279.4

_TOP_LEVEL_NUMBER = re.compile(r"^\s*\d+[.)、．]\s")
_SUB_LEVEL_NUMBER = re.compile(r"^\s*\(?[a-zＡ-Ｚ一二三四五六]\)?[.)、．]?\s", re.IGNORECASE)
_ANSWER_LINE = re.compile(r"_{3,}|…{3,}|答.?[：:]\s*$")
_MARKS_ZH = re.compile(r"[（(]\s*(\d+(?:\.\d+)?)\s*分\s*[）)]")


def _emus_to_mm(value: Length | None, default: float) -> float:
    return round(value.mm, 2) if value is not None else default


def _page_size(width: Length | None, height: Length | None) -> str:
    if width is None or height is None:
        return "A4"
    w, h = width.mm, height.mm
    if abs(w - A4_WIDTH_MM) < 5 and abs(h - A4_HEIGHT_MM) < 5:
        return "A4"
    if abs(w - LETTER_WIDTH_MM) < 5 and abs(h - LETTER_HEIGHT_MM) < 5:
        return "Letter"
    return "A4"  # unknown size -> default A4 (flag via unmapped)


def _style_font(style: Any) -> tuple[str, str, float | None]:
    """Return (latin_font, east_asia_font, size_pt) for a paragraph style."""
    latin = getattr(style.font, "name", None) or ""
    size_pt = style.font.size.pt if style.font.size else None
    east_asia = ""
    try:
        rpr = style.element.get_or_add_rPr()
        rfonts = rpr.find(qn("w:rFonts"))
        if rfonts is not None:
            east_asia = rfonts.get(qn("w:eastAsia")) or ""
    except Exception:  # pragma: no cover - defensive
        pass
    return latin, east_asia, size_pt


def _line_spacing(style: Any) -> float:
    ls = style.paragraph_format.line_spacing if style is not None else None
    if isinstance(ls, float) and ls > 0:
        return ls
    return 1.15


def _collect_text(container: Any) -> list[str]:
    return [p.text.strip() for p in container.paragraphs if p.text and p.text.strip()]


def _collect_all_text(doc: Any) -> list[str]:
    """Body text from top-level paragraphs AND table cells (in reading order)."""
    texts = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    if p.text and p.text.strip():
                        texts.append(p.text.strip())
    return texts


def _has_page_field(paragraph: Any) -> bool:
    xml = paragraph._p.xml
    return " PAGE " in xml or 'instrText' in xml and "PAGE" in xml


_ALIGN_MAP = {
    WD_ALIGN_PARAGRAPH.CENTER: "center",
    WD_ALIGN_PARAGRAPH.LEFT: "left",
    WD_ALIGN_PARAGRAPH.RIGHT: "right",
}

_LAYOUT_FIELDS = tuple(AnswerSheetLayoutConfig.model_fields)


def _is_mcq_table(tbl: Any) -> bool:
    if not tbl.rows:
        return False
    header = "".join(cell.text for cell in tbl.rows[0].cells)
    return "題號" in header and "答案" in header


def _detect_answer_sheet_layout(
    doc: Any,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Deterministically extract answer-sheet layout cues the renderer honours.

    Only high-confidence facts are detected (MCQ column groups/widths/alignment,
    hierarchy indent).  Everything else stays at its schema default and is
    reported back by the caller via ``defaults_used`` so the UI can label it
    "Default / Not detected" instead of faking a source value.
    """
    overrides: dict[str, Any] = {}
    detected: dict[str, dict[str, Any]] = {}

    mcq = next((tbl for tbl in doc.tables if _is_mcq_table(tbl)), None)
    if mcq is not None:
        header = [cell.text.strip() for cell in mcq.rows[0].cells]
        pairs = max(1, len(header) // 2)
        overrides["mcq_columns"] = min(pairs, 3)  # schema caps at 3 column-groups
        detected["mcq_columns"] = {
            "value": overrides["mcq_columns"],
            "confidence": 0.95,
            "source": "mcq_table",
        }

        widths = [round(c.width.mm, 1) for c in mcq.columns if c.width is not None]
        if len(widths) >= 2:
            overrides["mcq_question_width_mm"] = round(min(widths[0], 40.0), 1)
            overrides["mcq_answer_width_mm"] = round(min(widths[1], 50.0), 1)
            detected["mcq_question_width_mm"] = {
                "value": overrides["mcq_question_width_mm"],
                "confidence": 0.9,
                "source": "mcq_table",
            }
            detected["mcq_answer_width_mm"] = {
                "value": overrides["mcq_answer_width_mm"],
                "confidence": 0.9,
                "source": "mcq_table",
            }

        for cell in mcq.rows[0].cells:
            align = cell.paragraphs[0].alignment if cell.paragraphs else None
            mapped = _ALIGN_MAP.get(align)
            if mapped is not None:
                overrides["mcq_alignment"] = mapped
                detected["mcq_alignment"] = {
                    "value": mapped,
                    "confidence": 0.85,
                    "source": "mcq_table",
                }
                break

    # Hierarchy indent step: the left indent of sub-question paragraphs.
    # A flat (label/tab-only) source uses 0; an indented one uses a positive step.
    sub_indents: set[float] = set()
    for paragraph in doc.paragraphs:
        text = (paragraph.text or "").lstrip()
        if re.match(r"^\([a-z0-9]+\)", text, re.IGNORECASE) or re.match(
            r"^\((i|v|x)+\)", text, re.IGNORECASE
        ):
            li = paragraph.paragraph_format.left_indent
            sub_indents.add(round(li.mm, 1) if li is not None else 0.0)
    if sub_indents:
        step = max(sub_indents)
        overrides["hierarchy_indent_mm"] = step
        detected["hierarchy_indent_mm"] = {
            "value": step,
            "confidence": 0.85 if step == 0.0 else 0.7,
            "source": "paragraph_indent",
        }

    return overrides, detected


@dataclass
class TemplateImportDraft:
    profile: TemplateProfileImportDraft
    confidence: dict[str, float] = field(default_factory=dict)
    unmapped: list[str] = field(default_factory=list)
    detected_fields: dict[str, dict[str, Any]] = field(default_factory=dict)
    evidence: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    defaults_used: list[str] = field(default_factory=list)
    needs_review: bool = False


def import_template_docx(data: bytes) -> TemplateImportDraft:
    if not data:
        raise ValueError("empty DOCX data")
    doc = Document(BytesIO(data))
    section = doc.sections[0]
    normal = doc.styles["Normal"]

    page = {
        "size": _page_size(section.page_width, section.page_height),
        "margin_top_mm": _emus_to_mm(section.top_margin, 20.0),
        "margin_right_mm": _emus_to_mm(section.right_margin, 20.0),
        "margin_bottom_mm": _emus_to_mm(section.bottom_margin, 20.0),
        "margin_left_mm": _emus_to_mm(section.left_margin, 20.0),
    }

    latin, east_asia, size_pt = _style_font(normal)
    typography = {
        "chinese_font": east_asia or "Noto Sans CJK",
        "latin_font": latin or "Liberation Serif",
        "base_font_size_pt": size_pt or 12.0,
        "line_spacing": _line_spacing(normal),
    }

    header_text = " ".join(_collect_text(section.header)).strip()
    footer_text = " ".join(_collect_text(section.footer)).strip()
    footer_page = any(_has_page_field(p) for p in section.footer.paragraphs)

    # Numbering hints from body text ("1." vs "(1)", "(a)" vs "a)").
    body_paras = _collect_all_text(doc)
    # A body candidate is evidence only, not an accepted identity value.  The
    # unsaved import draft may therefore carry an empty school_name and the
    # strict create schema forces the teacher to confirm it before persistence.
    school_name = header_text
    body_school_candidate = next(
        (
            text
            for text in body_paras
            if text and len(text) <= 40 and not _MARKS_ZH.search(text)
        ),
        None,
    )
    question_style, sub_question_style = "1.", "(a)"
    q_confidence = 0.3
    s_confidence = 0.3
    for t in body_paras:
        if re.match(r"^\s*Q\d+[.)](?:\s|$)", t, re.IGNORECASE):
            question_style, q_confidence = "Q1.", 0.85
        elif re.match(r"^\s*\(\d+\)\s", t):
            question_style, q_confidence = "(1)", 0.8
        elif re.match(r"^\s*\d+[.)]\s", t):
            question_style, q_confidence = "1.", 0.8
        if re.match(r"^\s*\([a-z]\)\s", t, re.IGNORECASE):
            sub_question_style, s_confidence = "(a)", 0.8
        elif re.match(r"^\s*[a-z][.)]\s", t, re.IGNORECASE):
            sub_question_style, s_confidence = "a.", 0.8

    answer_lines = 0
    if any(_ANSWER_LINE.search(t) for t in body_paras):
        answer_lines = 1

    chinese_marks = any(_MARKS_ZH.search(t) for t in body_paras)
    marks_format = "（{marks}分）" if chinese_marks else "({marks} marks)"
    marks_display = "right"

    layout_overrides, layout_detected = _detect_answer_sheet_layout(doc)
    layout = {**AnswerSheetLayoutConfig().model_dump(), **layout_overrides}
    layout_defaults = [name for name in _LAYOUT_FIELDS if name not in layout_detected]

    unmapped: list[str] = []
    confidence: dict[str, float] = {}
    for key, conf in [
        ("page_config_json", 0.9),
        ("typography_config_json", 0.8),
        ("header_config_json", 0.9 if header_text else 0.1),
        ("footer_config_json", 0.8),
        ("numbering_config_json", min(q_confidence, s_confidence)),
        ("section_style_config_json", 0.1),
        ("question_style_config_json", 0.3),
    ]:
        confidence[key] = conf
    if not header_text:
        unmapped.append("header_text")
    if not footer_text:
        unmapped.append("footer_text")
    if not (east_asia and latin):
        unmapped.append("fonts")
    if answer_lines == 0:
        unmapped.append("answer_lines")

    profile = TemplateProfileImportDraft.model_validate(
        {
            "name": "Imported from DOCX",
            "school_name": school_name,
            "page_config_json": page,
            "typography_config_json": typography,
            "header_config_json": {"text": header_text},
            "footer_config_json": {"text": footer_text, "page_numbering": footer_page},
            "numbering_config_json": {
                "question_style": question_style,
                "sub_question_style": sub_question_style,
                "sub_sub_question_style": "roman",
            },
            "section_style_config_json": {"spacing_before_pt": 6.0, "spacing_after_pt": 6.0},
            "question_style_config_json": {
                "spacing_before_pt": 3.0,
                "spacing_after_pt": 3.0,
                "marks_display": marks_display,
                "marks_format": marks_format,
                "default_answer_lines": answer_lines,
            },
            "answer_sheet_layout_json": layout,
            "role_styles": {},
        }
    )
    detected_fields = {
        "school_name": {
            "value": header_text or None,
            "candidate": None if header_text else body_school_candidate,
            "confidence": 0.9 if header_text else (0.4 if body_school_candidate else 0.0),
            "review_required": not bool(header_text),
            "source": "header" if header_text else ("body" if body_school_candidate else None),
        },
        "header_text": {
            "value": header_text or None,
            "confidence": 0.9 if header_text else 0.0,
            "review_required": not bool(header_text),
            "source": "header" if header_text else None,
        },
        "footer_text": {
            "value": footer_text or None,
            "confidence": 0.8 if footer_text else 0.0,
            "review_required": not bool(footer_text),
            "source": "footer" if footer_text else None,
        },
    }
    detected_fields.update(
        {name: {**meta, "review_required": False} for name, meta in layout_detected.items()}
    )
    return TemplateImportDraft(
        profile=profile,
        confidence=confidence,
        unmapped=unmapped,
        detected_fields=detected_fields,
        evidence={
            "header": ([{"location": "header", "text": header_text}] if header_text else []),
            "footer": ([{"location": "footer", "text": footer_text}] if footer_text else []),
            "body_school_candidate": (
                [{"location": "body", "text": body_school_candidate}]
                if body_school_candidate and not header_text
                else []
            ),
        },
        defaults_used=layout_defaults,
        needs_review=bool(unmapped),
    )
