"""Deterministic splitter: pasted question-set text / .docx -> question drafts.

No LLM. Teacher-authored wording is preserved verbatim; marks are extracted
(kept in the text too — the draft is reviewable and the teacher can remove the
redundant mark token before saving, per the never-alter-content rule).
"""
from __future__ import annotations

import re
from decimal import Decimal
from io import BytesIO
from typing import Any

from docx import Document

from app.schemas.content import DocNode
from app.schemas.question import QuestionIngestDraft

_QUEST_START = re.compile(
    r"^\s*(?:Q(\d+)[.)]|第?\s*(\d+)\s*[題、.．)]|(\d+)[.)、．])\s"
)
_SECTION_HEADER = re.compile(
    r"^\s*(?:第[一二三四五六七八九十百]+[部章節]|[甲乙丙丁戊己庚辛壬癸]部|Part\s+[A-Z])\b",
    re.IGNORECASE,
)
_SUB_LEVEL1 = re.compile(r"^\s*\(?([a-zA-Z])\)?[.、．)]\s")
_SUB_LEVEL2 = re.compile(r"^\s*\(?(i{1,3}|iv|v|vi{0,3}|ix|x|I{1,3}|IV|V|VI{0,3}|IX|X)\)?[.、．)]\s")
_MARKS_EN = re.compile(r"\((\d+(?:\.\d+)?)\s*marks?\)", re.IGNORECASE)
_MARKS_ZH = re.compile(r"[（(](\d+(?:\.\d+)?)\s*分[）)]")
_WHITESPACE = re.compile(r"\s+")


def _extract_marks(text: str) -> Decimal:
    for pattern in (_MARKS_EN, _MARKS_ZH):
        match = pattern.search(text)
        if match:
            return Decimal(match.group(1))
    return Decimal("0")


_QUESTION_LABEL = re.compile(r"^\s*Q\s*(\d+)\s*[.)]?\s*$", re.IGNORECASE)
_SUB_LABEL_ONLY = re.compile(r"^\s*\(?([a-zA-Z])\)?\s*$")
_SUBSUB_LABEL_ONLY = re.compile(
    r"^\s*\(?\s*(i{1,3}|iv|v|vi{0,3}|ix|x|I{1,3}|IV|V|VI{0,3}|IX|X)\s*\)?\s*$"
)


def _classify_cells(cells: list[str]) -> tuple[str, str, str, str, str]:
    """Return (q_label, sub_label, subsub_label, text, marks_text) for one row."""
    q = sub = subsub = marks = ""
    parts: list[str] = []
    for raw in cells:
        c = raw.strip()
        if not c:
            continue
        if _QUESTION_LABEL.match(c):
            q = c
        elif _SUBSUB_LABEL_ONLY.match(c) and sub:
            subsub = c
        elif _SUB_LABEL_ONLY.match(c):
            sub = c
        elif _MARKS_ZH.search(c) or _MARKS_EN.search(c):
            marks = f"{marks} {c}".strip()
        else:
            parts.append(c)
    return q, sub, subsub, " ".join(parts), marks


def _table_to_drafts(tables: Any) -> list[QuestionIngestDraft]:
    """Parse the [Q, sub, sub-sub, answer, marks] table shape into drafts.

    Tables with no ``Q<num>.`` cell (e.g. the MC answer grid) are skipped.
    """
    drafts: list[QuestionIngestDraft] = []
    current: dict | None = None
    current_index = 0

    def new_question(q_label: str) -> dict:
        return {"label": q_label, "total": Decimal("0"), "blocks": [], "sub": None, "subsub": None}

    def add_text(text: str) -> None:
        if not text or current is None:
            return
        node = _paragraph_node(text)
        target = current["subsub"] or current["sub"]
        if target is not None:
            target["content"].append(node)
        else:
            current["blocks"].append(node)

    def finish() -> None:
        nonlocal current
        if current is None:
            return
        blocks = current["blocks"]
        if not blocks:
            blocks = [_paragraph_node("")]
        for block in blocks:
            _fill_empty_subquestions(block)
        drafts.append(
            QuestionIngestDraft(
                internal_title=_title_from(current["label"], current_index + 1),
                subject="", level="", tags_json=[], source_note=None,
                marks=current["total"], status="draft",
                content_json=_build_doc(blocks),
            )
        )

    for table in tables:
        if not any(_QUESTION_LABEL.match(c.text) for row in table.rows for c in row.cells):
            continue  # not the structured-question layout
        for row in table.rows:
            q, sub, subsub, text, marks_cell = _classify_cells([c.text for c in row.cells])
            if q:
                if current is not None:
                    finish()
                    current_index += 1
                current = new_question(q)
            if current is None:
                continue
            if sub:
                current["sub"] = {
                    "type": "subQuestion",
                    "attrs": {"label": _normalize_label(sub)},
                    "content": [],
                }
                current["blocks"].append(current["sub"])
                current["subsub"] = None
            if subsub and current["sub"] is not None:
                current["subsub"] = {
                    "type": "subQuestion",
                    "attrs": {"label": _normalize_label(subsub)},
                    "content": [],
                }
                current["sub"]["content"].append(current["subsub"])
            if text:
                add_text(text)
            if marks_cell:
                current["total"] += _extract_marks(marks_cell)
    if current is not None:
        finish()
    return drafts


def _normalize_label(raw: str) -> str:
    token = _WHITESPACE.sub("", raw).strip("()")
    if token.isascii() and token.isalpha():
        return f"({token.lower()})"
    # CJK numerals or anything else: keep as written (lowercase latin if any)
    return f"({token})"


def _paragraph_node(text: str) -> dict:
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def _fill_empty_subquestions(block: dict) -> None:
    """Ensure every subQuestion node has ≥1 child block (schema enforces min_length=1)."""
    if block.get("type") == "subQuestion" and not block.get("content"):
        block["content"] = [_paragraph_node("")]
    for child in block.get("content", []):
        if isinstance(child, dict):
            _fill_empty_subquestions(child)


def _title_from(first_line: str, index: int) -> str:
    clean = _WHITESPACE.sub(" ", first_line).strip()
    if len(clean) > 40:
        clean = clean[:40].rstrip() + "…"
    return clean or f"Question {index}"


def _build_doc(blocks: list[dict]) -> DocNode:
    # Validate through the strict canonical schema so drafts are save-ready.
    return DocNode.model_validate({"type": "doc", "content": blocks})


def _split_questions(paragraphs: list[str]) -> list[list[str]]:
    """Group paragraphs into question blocks, skipping section headers."""
    questions: list[list[str]] = []
    current: list[str] = []
    for para in paragraphs:
        if _SECTION_HEADER.match(para):
            if current:
                questions.append(current)
                current = []
            continue
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
    current_subsub: dict | None = None

    def flush_para() -> None:
        nonlocal current_para
        if not current_para:
            return
        text = " ".join(current_para).strip()
        current_para = []
        if not text:
            return
        target = current_subsub or current_sub
        if target is not None:
            target["content"].append(_paragraph_node(text))
        else:
            blocks.append(_paragraph_node(text))

    for line in block:
        sub2_match = _SUB_LEVEL2.match(line)
        sub1_match = _SUB_LEVEL1.match(line)
        if sub2_match and current_sub is not None:
            flush_para()
            current_subsub = {
                "type": "subQuestion",
                "attrs": {"label": _normalize_label(sub2_match.group(1))},
                "content": [],
            }
            current_sub["content"].append(current_subsub)
            sub_text = _SUB_LEVEL2.sub("", line).strip()
            if sub_text:
                current_subsub["content"].append(_paragraph_node(sub_text))
        elif sub1_match:
            flush_para()
            current_sub = {
                "type": "subQuestion",
                "attrs": {"label": _normalize_label(sub1_match.group(1))},
                "content": [],
            }
            current_subsub = None
            blocks.append(current_sub)
            sub_text = _SUB_LEVEL1.sub("", line).strip()
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
    """Split paragraphs AND tables from an uploaded .docx into reviewable drafts."""
    if not data or not data[:4] == b"PK\x03\x04":
        raise ValueError("not a valid DOCX file")
    doc = Document(BytesIO(data))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
    paragraph_drafts = [
        _draft_from_block(block, i + 1)
        for i, block in enumerate(_split_questions(paragraphs))
    ]
    table_drafts = _table_to_drafts(doc.tables)
    return paragraph_drafts + table_drafts