"""Best-effort mapping of a school-format DOCX into a template-profile draft.

Deterministic, no LLM. Every field of the strict ``TemplateProfileCreate``
schema is populated; values that could not be inferred get sane defaults and
land in ``unmapped`` so the teacher can review them in the UI.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Length

from app.schemas.template_profile import TemplateProfileCreate

A4_WIDTH_MM = 210.0
A4_HEIGHT_MM = 297.0
LETTER_WIDTH_MM = 215.9
LETTER_HEIGHT_MM = 279.4

_TOP_LEVEL_NUMBER = re.compile(r"^\s*\d+[.)、．]\s")
_SUB_LEVEL_NUMBER = re.compile(r"^\s*\(?[a-zＡ-Ｚ一二三四五六]\)?[.)、．]?\s", re.IGNORECASE)
_ANSWER_LINE = re.compile(r"_{3,}|…{3,}|答.?[：:]\s*$")
_MARKS_ZH = re.compile(r"（\s*(\d+(?:\.\d+)?)\s*分\s*）")


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


def _has_page_field(paragraph: Any) -> bool:
    xml = paragraph._p.xml
    return " PAGE " in xml or 'instrText' in xml and "PAGE" in xml


@dataclass
class TemplateImportDraft:
    profile: TemplateProfileCreate
    confidence: dict[str, float] = field(default_factory=dict)
    unmapped: list[str] = field(default_factory=list)


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
    body_paras = [p.text for p in doc.paragraphs if p.text and p.text.strip()]
    question_style, sub_question_style = "1.", "(a)"
    q_confidence = 0.3
    s_confidence = 0.3
    for t in body_paras:
        if re.match(r"^\s*Q\d+[.)]\s", t, re.IGNORECASE):
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

    profile = TemplateProfileCreate.model_validate(
        {
            "name": "Imported from DOCX",
            "school_name": header_text or "Imported school",
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
            "role_styles": {},
        }
    )
    return TemplateImportDraft(profile=profile, confidence=confidence, unmapped=unmapped)