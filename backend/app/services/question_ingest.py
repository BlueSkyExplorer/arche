"""Deterministic splitter: pasted question-set text / .docx -> question drafts.

No LLM. Teacher-authored wording is preserved verbatim; marks are extracted
(kept in the text too — the draft is reviewable and the teacher can remove the
redundant mark token before saving, per the never-alter-content rule).
"""
from __future__ import annotations

import re
from decimal import Decimal
from io import BytesIO

from docx import Document

from app.schemas.content import DocNode
from app.schemas.question import QuestionIngestDraft

_QUEST_START = re.compile(r"^\s*(\d+)[.)、．]\s+")
_SUB_START = re.compile(r"^\s*\(?([a-zA-Z一二三四五六七八九十]+)\)?[.、．)]\s+")
_MARKS_EN = re.compile(r"\((\d+(?:\.\d+)?)\s*marks?\)", re.IGNORECASE)
_MARKS_ZH = re.compile(r"（(\d+(?:\.\d+)?)\s*分）")
_WHITESPACE = re.compile(r"\s+")


def _extract_marks(text: str) -> Decimal:
    for pattern in (_MARKS_EN, _MARKS_ZH):
        match = pattern.search(text)
        if match:
            return Decimal(match.group(1))
    return Decimal("0")


def _normalize_label(raw: str) -> str:
    token = _WHITESPACE.sub("", raw).strip("()")
    if token.isascii() and token.isalpha():
        return f"({token.lower()})"
    # CJK numerals or anything else: keep as written (lowercase latin if any)
    return f"({token})"


def _paragraph_node(text: str) -> dict:
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def _title_from(first_line: str, index: int) -> str:
    clean = _WHITESPACE.sub(" ", first_line).strip()
    if len(clean) > 40:
        clean = clean[:40].rstrip() + "…"
    return clean or f"Question {index}"


def _build_doc(blocks: list[dict]) -> DocNode:
    # Validate through the strict canonical schema so drafts are save-ready.
    return DocNode.model_validate({"type": "doc", "content": blocks})


def _split_questions(paragraphs: list[str]) -> list[list[str]]:
    """Group paragraphs into question blocks, keyed on top-level numbers."""
    questions: list[list[str]] = []
    current: list[str] = []
    for para in paragraphs:
        if _QUEST_START.match(para):
            if current:
                questions.append(current)
            current = [para]
        elif current or questions:
            current.append(para)
    if current:
        questions.append(current)
    return questions


def _draft_from_block(block: list[str], index: int) -> QuestionIngestDraft:
    first = _QUEST_START.sub("", block[0]).strip()
    marks = _extract_marks(" ".join(block))
    blocks: list[dict] = []
    current_para: list[str] = []
    current_sub: dict | None = None

    def flush_para() -> None:
        nonlocal current_para
        if not current_para:
            return
        text = " ".join(current_para).strip()
        current_para = []
        if not text:
            return
        if current_sub is not None:
            current_sub["content"].append(_paragraph_node(text))
        else:
            blocks.append(_paragraph_node(text))

    for line in block:
        match = _SUB_START.match(line)
        if match:
            flush_para()
            current_sub = {
                "type": "subQuestion",
                "attrs": {"label": _normalize_label(match.group(1))},
                "content": [],
            }
            blocks.append(current_sub)
            sub_text = _SUB_START.sub("", line).strip()
            if sub_text:
                current_sub["content"].append(_paragraph_node(sub_text))
        else:
            current_para.append(line)
    flush_para()

    # If the first line carried marks-only text like "(2 marks)", ensure the
    # question has at least one body paragraph.
    if not blocks:
        blocks.append(_paragraph_node(first))

    return QuestionIngestDraft(
        internal_title=_title_from(first, index),
        subject="",
        level="",
        tags_json=[],
        source_note=None,
        marks=marks,
        status="draft",
        content_json=_build_doc(blocks),
    )


def ingest_question_text(text: str) -> list[QuestionIngestDraft]:
    """Split pasted question-set text into reviewable drafts (list of dicts)."""
    paragraphs = [p.strip() for p in text.splitlines() if p.strip()]
    questions = _split_questions(paragraphs)
    return [_draft_from_block(block, i + 1) for i, block in enumerate(questions)]


def ingest_question_docx(data: bytes) -> list[QuestionIngestDraft]:
    """Split paragraphs from an uploaded .docx into reviewable drafts."""
    if not data or not data[:4] == b"PK\x03\x04":
        raise ValueError("not a valid DOCX file")
    doc = Document(BytesIO(data))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
    questions = _split_questions(paragraphs)
    return [_draft_from_block(block, i + 1) for i, block in enumerate(questions)]