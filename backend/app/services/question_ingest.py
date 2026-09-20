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
from uuid import UUID

from docx import Document

from app.schemas.content import DocNode
from app.schemas.question import DeclaredMark, QuestionIngestDraft
from app.services.ai_client import AIClient, AIClientError
from app.services.ai_schema import AIQuestion, ai_questions_to_drafts
from app.services.docx_images import extract_cell_images

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
_MULTIPLIER = re.compile(r"\s*[x×]\s*(\d+(?:\.\d+)?)")
_WHITESPACE = re.compile(r"\s+")


def _document_skeleton(doc: Any) -> str:
    lines = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    for ti, table in enumerate(doc.tables):
        lines.append(f"--- table {ti} ({len(table.columns)} cols) ---")
        for row in table.rows:
            lines.append(" | ".join(c.text.strip() for c in row.cells))
    return "\n".join(lines)


def _suggest_questions_ai(skeleton: str, client: AIClient) -> list[AIQuestion]:
    system = (
        "你是香港試卷結構辨識器。把文字與表格切分成題目與子題，標出分數(marks)與"
        "子題label(如 (a)/(i))。只輸出JSON:{questions:[{label,marks,stem,subparts:"
        "[{label,text,marks,children:[...]}]}]}。不得改寫任何答案文字。"
    )
    obj = client.complete_json(
        [{"role": "system", "content": system}, {"role": "user", "content": skeleton}]
    )
    return [AIQuestion.model_validate(q) for q in obj.get("questions", [])]


def _parse_marks(text: str, location: str = "") -> tuple[Decimal, list[DeclaredMark]]:
    """Sum all mark tokens (applying xN/×N multipliers) and record each stated
    token as declared evidence at the given location. No marks -> (0, [])."""
    total = Decimal("0")
    declared: list[DeclaredMark] = []
    for pattern in (_MARKS_EN, _MARKS_ZH):
        for match in pattern.finditer(text):
            base = Decimal(match.group(1))
            # Look for a multiplier right after the mark token
            after = text[match.end() :]
            mult_match = _MULTIPLIER.match(after)
            if mult_match:
                base *= Decimal(mult_match.group(1))
            total += base
            declared.append(DeclaredMark(value=base, raw_text=match.group(0), location=location))
    return total, declared


def _extract_marks(text: str) -> Decimal:
    """Sum all mark tokens, applying xN/×N multipliers when present.

    Handles patterns like ``(1分)x3`` or ``(2 marks)×2`` — the multiplier
    immediately following a mark token means the per-answer mark times N
    acceptable answers.  When no multiplier follows, the mark stands alone.
    """
    return _parse_marks(text)[0]


def _declared_mismatch(declared: list[DeclaredMark]) -> str | None:
    """Return a human-readable mismatch when a stated question-level total does
    not equal the sum of the stated sub-part (leaf) marks; else None."""
    total = sum((m.value for m in declared if m.location == ""), Decimal("0"))
    leaves = sum((m.value for m in declared if m.location != ""), Decimal("0"))
    if total > 0 and leaves > 0 and total != leaves:
        return f"Declared total {total} ≠ computed leaf total {leaves}"
    return None


_QUESTION_LABEL = re.compile(
    r"^\s*(?:Q\s*\d+\s*[.)]?|第?\s*\d+\s*題|\d+\s*[.)、．])\s*$",
    re.IGNORECASE,
)
_SUB_LABEL_ONLY = re.compile(r"^\s*\(?([a-zA-Z])\)?\s*$")
_SUBSUB_LABEL_ONLY = re.compile(
    r"^\s*\(?\s*(i{1,3}|iv|v|vi{0,3}|ix|x|I{1,3}|IV|V|VI{0,3}|IX|X)\s*\)?\s*$"
)


def _classify_cells(cells: list[str], has_sub: bool = False) -> tuple[str, str, str, str, str]:
    """Return (q_label, sub_label, subsub_label, text, marks_text) for one row.

    ``has_sub`` lets a continuation row (whose sub-part cell is empty but whose
    sub-sub-part cell is set, e.g. ``(ii)``) attach to the current sub-part.
    """
    q = sub = subsub = marks = ""
    parts: list[str] = []
    for raw in cells:
        c = raw.strip()
        if not c:
            continue
        if _QUESTION_LABEL.match(c):
            q = c
        elif _SUBSUB_LABEL_ONLY.match(c) and (sub or has_sub):
            subsub = c
        elif _SUB_LABEL_ONLY.match(c):
            sub = c
        elif _MARKS_ZH.search(c) or _MARKS_EN.search(c):
            marks = f"{marks} {c}".strip()
        else:
            parts.append(c)
    return q, sub, subsub, " ".join(parts), marks


def _table_to_drafts(
    tables: Any, cell_images: dict[tuple[int, int, int], bytes] | None = None
) -> tuple[list[QuestionIngestDraft], list[dict]]:
    """Parse the [Q, sub, sub-sub, answer, marks] table shape into drafts.

    Tables with no ``Q<num>.`` cell (e.g. the MC answer grid) are skipped.
    Returns (drafts, image_attachments) where each attachment is
    {"draft_index", "label" (sub-sub/sub label or None), "image" (bytes)}.
    """
    drafts: list[QuestionIngestDraft] = []
    attachments: list[dict] = []
    current: dict | None = None
    current_index = 0

    def new_question(q_label: str) -> dict:
        return {
            "label": q_label,
            "total": Decimal("0"),
            "declared": [],
            "blocks": [],
            "sub": None,
            "subsub": None,
        }

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
        draft_declared = current["declared"]
        validation_issues: list[str] = []
        mismatch = _declared_mismatch(draft_declared)
        if mismatch is not None:
            validation_issues.append(mismatch)
        drafts.append(
            QuestionIngestDraft(
                internal_title=_title_from(current["label"], current_index + 1),
                subject="", level="", tags_json=[], source_note=None,
                marks=current["total"] if draft_declared else None,
                declared_marks=draft_declared,
                needs_review=(not draft_declared) or bool(validation_issues),
                validation_issues=validation_issues,
                status="draft",
                content_json=_build_doc(blocks),
            )
        )

    for table_index, table in enumerate(tables):
        if not any(_QUESTION_LABEL.match(c.text) for row in table.rows for c in row.cells):
            continue  # not the structured-question layout
        for row_index, row in enumerate(table.rows):
            q, sub, subsub, text, marks_cell = _classify_cells(
                [c.text for c in row.cells],
                has_sub=current is not None and current["sub"] is not None,
            )
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
                sub_node = current.get("sub")
                subsub_node = current.get("subsub")
                location = ""
                if sub_node is not None:
                    location += sub_node["attrs"]["label"]
                if subsub_node is not None:
                    location += subsub_node["attrs"]["label"]
                total, declared = _parse_marks(marks_cell, location=location)
                current["total"] += total
                current["declared"].extend(declared)
            if cell_images and current is not None:
                for ci in range(len(row.cells)):
                    img = cell_images.get((table_index, row_index, ci))
                    if img is not None:
                        target = current.get("subsub") or current.get("sub")
                        attachments.append(
                            {
                                "draft_index": current_index,
                                "label": target["attrs"]["label"] if target else None,
                                "image": img,
                            }
                        )
    if current is not None:
        finish()
    return drafts, attachments


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
    # The question's total marks live on the stem line ("Q1. ... (2分)");
    # sub-part marks are captured as declared evidence at their location, and
    # a mark token on a line we cannot attribute gets flagged for review.
    stem_marks, declared = _parse_marks(block[0], location="")
    stem_has_marks = bool(declared)
    ambiguous = False
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

    for idx, line in enumerate(block):
        sub2_match = _SUB_LEVEL2.match(line)
        sub1_match = _SUB_LEVEL1.match(line)
        if sub2_match and current_sub is not None:
            flush_para()
            label = _normalize_label(sub2_match.group(1))
            current_subsub = {
                "type": "subQuestion",
                "attrs": {"label": label},
                "content": [],
            }
            current_sub["content"].append(current_subsub)
            _, sub_declared = _parse_marks(
                line, location=current_sub["attrs"]["label"] + label
            )
            declared.extend(sub_declared)
            sub_text = _SUB_LEVEL2.sub("", line).strip()
            if sub_text:
                current_subsub["content"].append(_paragraph_node(sub_text))
        elif sub1_match:
            flush_para()
            label = _normalize_label(sub1_match.group(1))
            current_sub = {
                "type": "subQuestion",
                "attrs": {"label": label},
                "content": [],
            }
            current_subsub = None
            blocks.append(current_sub)
            _, sub_declared = _parse_marks(line, location=label)
            declared.extend(sub_declared)
            sub_text = _SUB_LEVEL1.sub("", line).strip()
            if sub_text:
                current_sub["content"].append(_paragraph_node(sub_text))
        else:
            if idx > 0:
                _, body_declared = _parse_marks(line, location="")
                if body_declared:
                    ambiguous = True
            current_para.append(line)
    flush_para()

    # If the first line carried marks-only text like "(2 marks)", ensure the
    # question has at least one body paragraph.
    if not blocks:
        blocks.append(_paragraph_node(first))

    validation_issues: list[str] = []
    mismatch = _declared_mismatch(declared)
    if mismatch is not None:
        validation_issues.append(mismatch)

    return QuestionIngestDraft(
        internal_title=_title_from(first, index),
        subject="",
        level="",
        tags_json=[],
        source_note=None,
        marks=stem_marks if stem_has_marks else None,
        declared_marks=declared,
        needs_review=(not declared) or ambiguous or bool(validation_issues),
        validation_issues=validation_issues,
        status="draft",
        content_json=_build_doc(blocks),
    )


def ingest_question_text(text: str) -> list[QuestionIngestDraft]:
    """Split pasted question-set text into reviewable drafts (list of dicts)."""
    paragraphs = [p.strip() for p in text.splitlines() if p.strip()]
    questions = _split_questions(paragraphs)
    return [_draft_from_block(block, i + 1) for i, block in enumerate(questions)]


def _insert_image_into(blocks: list, label: str | None, asset_id: UUID) -> None:
    from app.schemas.content import ImageAttrs, ImageNode

    node = ImageNode(type="image", attrs=ImageAttrs(asset_id=asset_id))
    if label is None:
        blocks.insert(0, node)
        return
    for b in blocks:
        if getattr(b, "type", None) == "subQuestion":
            if getattr(b.attrs, "label", None) == label:
                b.content.append(node)
                return
            _insert_image_into(b.content, label, asset_id)


def attach_image_assets(
    drafts: list[QuestionIngestDraft],
    attachments: list[dict],
    asset_ids: list[UUID],
) -> None:
    """Mutate drafts in place: insert an ImageNode(asset_id) at each attachment."""
    for att, asset_id in zip(attachments, asset_ids, strict=True):
        draft = drafts[att["draft_index"]]
        _insert_image_into(draft.content_json.content, att["label"], asset_id)


def _ingest_with_images(
    data: bytes, doc: Any
) -> tuple[list[QuestionIngestDraft], list[dict]]:
    """Parse paragraphs + tables, returning (drafts, image_attachments)."""
    if _is_answer_sheet(doc):
        return _parse_answer_sheet(doc), []
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
    paragraph_drafts = [
        _draft_from_block(block, i + 1)
        for i, block in enumerate(_split_questions(paragraphs))
    ]
    table_drafts, attachments = _table_to_drafts(doc.tables, extract_cell_images(doc))
    drafts = paragraph_drafts + table_drafts
    if not drafts:
        from app.core.config import get_settings

        client = AIClient(get_settings())
        if client.enabled:
            try:
                drafts = ai_questions_to_drafts(
                    _suggest_questions_ai(_document_skeleton(doc), client)
                )
            except AIClientError:
                drafts = []
    return drafts, attachments


# ---------------------------------------------------------------------------
# Answer-sheet import: HKDSE fused-label format (e.g. "1ai", "2a", "1M").
# An answers document carries question numbers fused with sub-part labels
# (no "1." / "(a)" delimiters) and bare "1M"/"1m" mark tokens, which the
# standard question-paper splitter above does not recognise.
# ---------------------------------------------------------------------------

_ANSWER_MARK = re.compile(r"^\d+(?:\.\d+)?[mM]$")
_FUSED_Q = re.compile(r"^(\d+)([a-z])(i{1,3}|iv|v|vi{0,3}|ix|x)?$")
_FUSED_SUB = re.compile(r"^([a-z])(i{1,3}|iv|v|vi{0,3}|ix|x)?$")
_FUSED_SUBSUB = re.compile(r"^(i{1,3}|iv|v|vi{0,3}|ix|x)$")
_TRAILING_MARK = re.compile(r"(?:\t+| {2,})(\d+(?:\.\d+)?)[mM]\s*$")
_PAPER_HEADER = re.compile(r"^Paper\s*\d*\s*(?:Section\s*[A-Z])?", re.IGNORECASE)


def _classify_answer_token(raw: str) -> tuple[str, str, str | None, str | None] | None:
    """Classify a whitespace-normalised answer-sheet label/mark token.

    Returns ``(kind, a, b, c)``: ``mark`` (a=value) / ``question``
    (a=qnum, b=sub, c=subsub) / ``sub`` (a=sub, b=subsub) / ``subsub``
    (a=subsub); ``None`` when the token is ordinary text.
    """
    token = _WHITESPACE.sub("", raw).strip().lower()
    if not token:
        return None
    if _ANSWER_MARK.match(token):
        return ("mark", token[:-1], None, None)
    m = _FUSED_Q.match(token)
    if m and m.group(2) != "m":
        return ("question", m.group(1), m.group(2), m.group(3))
    if token.isdigit():
        return ("question", token, None, None)
    m = _FUSED_SUBSUB.match(token)
    if m:
        return ("subsub", m.group(1), None, None)
    m = _FUSED_SUB.match(token)
    if m and m.group(1) != "m":
        return ("sub", m.group(1), m.group(2), None)
    return None


def _strip_trailing_mark(text: str) -> tuple[str, str | None]:
    """Split a trailing ``1M``/``1m`` token off answer text, if present."""
    m = _TRAILING_MARK.search(text)
    if m:
        return text[: m.start()].rstrip(), m.group(1)
    return text, None


def _answer_sheet_table_items(tables: Any) -> list[tuple]:
    """Flatten 3-column answer tables ([label, answer, marks]) into tokens.

    Vertically-merged cells (same ``_tc`` element across consecutive rows) are
    only read once, so a merged ``10`` label / long answer does not repeat.
    """
    items: list[tuple] = []
    for table in tables:
        if len(table.columns) != 3:
            continue
        prev_tc: tuple | None = None
        for row in table.rows:
            cells = list(row.cells)
            label = text = mark = ""
            if len(cells) >= 3:
                label = cells[0].text.strip()
                text = cells[1].text.strip()
                mark = cells[2].text.strip()
            if prev_tc is not None and len(cells) >= 3:
                if cells[0]._tc is prev_tc[0]:
                    label = ""
                if cells[1]._tc is prev_tc[1]:
                    text = ""
                if cells[2]._tc is prev_tc[2]:
                    mark = ""
            prev_tc = tuple(c._tc for c in cells) if len(cells) >= 3 else None
            kind = _classify_answer_token(label)
            if kind:
                items.append(kind)
            elif label:
                items.append(("text", label))
            for line in text.split("\n"):
                body, trail = _strip_trailing_mark(line.strip())
                if body:
                    items.append(("text", body))
                if trail:
                    items.append(("mark", trail))
            if mark:
                mkind = _classify_answer_token(mark)
                items.append(("mark", mkind[1]) if mkind and mkind[0] == "mark" else ("text", mark))
    return items


def _split_label_and_text(line: str) -> tuple[list[tuple], str]:
    """Split a tab-separated answer line into leading label tokens + remaining text.

    ``b␉i␉answer`` → ([sub ``b``, subsub ``i``], ``answer``); ``3␉a␉i␉text`` →
    ([question ``3``, sub ``a``, subsub ``i``], ``text``). Returns ([], line)
    when the line does not begin with a label.
    """
    tokens = [t.strip() for t in line.split("\t")]
    label_tokens: list[tuple] = []
    for token in tokens:
        kind = _classify_answer_token(token)
        if kind and kind[0] in ("question", "sub", "subsub"):
            label_tokens.append(kind)
        else:
            break
    if not label_tokens:
        return [], line
    return label_tokens, "\t".join(tokens[len(label_tokens) :]).strip()


def _answer_sheet_paragraph_items(paragraphs: list[str]) -> list[tuple]:
    """Flatten answer-sheet paragraphs (fused labels + trailing marks) into tokens."""
    items: list[tuple] = []
    for para in paragraphs:
        text = para.strip()
        if not text:
            continue
        if _PAPER_HEADER.match(text) or _SECTION_HEADER.match(text):
            continue
        kind = _classify_answer_token(text)
        if kind:
            items.append(kind)
            continue
        label_tokens, remaining = _split_label_and_text(text)
        if label_tokens:
            items.extend(label_tokens)
            body, trail = _strip_trailing_mark(remaining)
            if body:
                items.append(("text", body))
            if trail:
                items.append(("mark", trail))
            continue
        body, trail = _strip_trailing_mark(text)
        if body:
            items.append(("text", body))
        if trail:
            items.append(("mark", trail))
    return items


def _new_answer_question(num: str, title: str) -> dict:
    return {
        "num": num,
        "title": title,
        "blocks": [],
        "sub": None,
        "subsub": None,
        "leaf_marks": Decimal("0"),
        "total": Decimal("0"),
        "declared": [],
        "has_sub": False,
    }


def _answer_location(cur: dict) -> str:
    parts = []
    if cur["sub"] is not None:
        parts.append(cur["sub"]["attrs"]["label"])
    if cur["subsub"] is not None:
        parts.append(cur["subsub"]["attrs"]["label"])
    return "".join(parts)


def _answer_finalize_leaf(cur: dict) -> None:
    leaf = cur["subsub"] or cur["sub"]
    if leaf is not None and cur["leaf_marks"] > 0:
        leaf["attrs"]["marks"] = str(cur["leaf_marks"])
    cur["leaf_marks"] = Decimal("0")


def _answer_set_sub(cur: dict, sub: str, subsub: str | None) -> None:
    _answer_finalize_leaf(cur)
    node = {"type": "subQuestion", "attrs": {"label": _normalize_label(sub)}, "content": []}
    cur["blocks"].append(node)
    cur["sub"] = node
    cur["subsub"] = None
    cur["has_sub"] = True
    if subsub:
        _answer_set_subsub(cur, subsub)


def _answer_set_subsub(cur: dict, subsub: str) -> None:
    _answer_finalize_leaf(cur)
    if cur["sub"] is None:
        return
    node = {"type": "subQuestion", "attrs": {"label": _normalize_label(subsub)}, "content": []}
    cur["sub"]["content"].append(node)
    cur["subsub"] = node


def _answer_add_text(cur: dict, text: str) -> None:
    if not text:
        return
    node = _paragraph_node(text)
    target = cur["subsub"] or cur["sub"]
    if target is not None:
        target["content"].append(node)
    else:
        cur["blocks"].append(node)


def _answer_finish(cur: dict) -> QuestionIngestDraft | None:
    if cur is None:
        return None
    _answer_finalize_leaf(cur)
    if not cur["blocks"]:
        cur["blocks"] = [_paragraph_node("")]
    for block in cur["blocks"]:
        _fill_empty_subquestions(block)
    if cur["has_sub"]:
        doc = _build_doc(cur["blocks"])
    else:
        doc = DocNode.model_validate(
            {
                "type": "doc",
                "marks": str(cur["total"]) if cur["total"] > 0 else None,
                "content": cur["blocks"],
            }
        )
    return QuestionIngestDraft(
        internal_title=cur["title"],
        subject="",
        level="",
        tags_json=[],
        source_note=None,
        marks=cur["total"] if cur["declared"] else None,
        declared_marks=cur["declared"],
        needs_review=not cur["declared"],
        validation_issues=[],
        status="draft",
        content_json=doc,
    )


def _build_answer_drafts(items: list[tuple]) -> list[QuestionIngestDraft]:
    drafts: list[QuestionIngestDraft] = []
    cur: dict | None = None
    for item in items:
        kind = item[0]
        if kind == "question":
            if cur is not None and cur["num"] == item[1]:
                # same question number → a further sub-part (or a merged-cell
                # repeat), not a new question
                if item[2]:
                    _answer_set_sub(cur, item[2], item[3])
                continue
            if cur is not None:
                draft = _answer_finish(cur)
                if draft is not None:
                    drafts.append(draft)
            title = _title_from(f"{item[1]}{item[2] or ''}{item[3] or ''}", len(drafts) + 1)
            cur = _new_answer_question(item[1], title)
            if item[2]:
                _answer_set_sub(cur, item[2], item[3])
        elif kind == "sub" and cur is not None:
            _answer_set_sub(cur, item[1], item[2])
        elif kind == "subsub" and cur is not None:
            _answer_set_subsub(cur, item[1])
        elif kind == "mark" and cur is not None:
            value = Decimal(item[1])
            cur["leaf_marks"] += value
            cur["total"] += value
            cur["declared"].append(
                DeclaredMark(value=value, raw_text=f"{item[1]}M", location=_answer_location(cur))
            )
        elif kind == "text" and cur is not None:
            _answer_add_text(cur, item[1])
    if cur is not None:
        draft = _answer_finish(cur)
        if draft is not None:
            drafts.append(draft)
    return drafts


def _is_answer_sheet(doc: Any) -> bool:
    """True when the document uses fused labels (``1ai``) plus ``1M`` marks."""
    texts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                texts.extend(p.text for p in cell.paragraphs)
    has_mark = False
    has_fused = False
    for text in texts:
        stripped = text.strip()
        if _ANSWER_MARK.match(stripped):
            has_mark = True
        if _FUSED_Q.match(_WHITESPACE.sub("", stripped).lower()):
            has_fused = True
    return has_mark and has_fused


def _mcq_answer_grid_drafts(tables: Any) -> list[QuestionIngestDraft]:
    """Create review drafts from ``Question no. / Answer`` MCQ grids.

    These rows contain answer keys rather than question stems, so marks remain
    unknown and every draft stays ``needs_review``. Repeated visual cells from
    Word horizontal merges are collapsed by their shared ``_tc`` identity.
    """
    drafts: list[QuestionIngestDraft] = []
    for table in tables:
        texts = [c.text.strip().casefold() for row in table.rows for c in row.cells]
        if "question no." not in texts or "answer" not in texts:
            continue
        for row in table.rows:
            unique: list[str] = []
            seen: set[int] = set()
            for cell in row.cells:
                key = id(cell._tc)
                if key in seen:
                    continue
                seen.add(key)
                text = _WHITESPACE.sub(" ", cell.text).strip()
                if text:
                    unique.append(text)
            index = 0
            while index + 1 < len(unique):
                number, answer = unique[index], unique[index + 1]
                if number.isdigit() and re.fullmatch(r"[A-D]", answer, re.IGNORECASE):
                    drafts.append(
                        QuestionIngestDraft(
                            internal_title=number,
                            subject="",
                            level="",
                            tags_json=[],
                            source_note="MCQ answer key; question stem absent from source",
                            marks=None,
                            declared_marks=[],
                            needs_review=True,
                            validation_issues=[],
                            status="draft",
                            content_json=_build_doc([_paragraph_node(f"Answer: {answer.upper()}")]),
                        )
                    )
                    index += 2
                else:
                    index += 1
    drafts.sort(key=lambda draft: int(draft.internal_title))
    return drafts


def _parse_answer_sheet(doc: Any) -> list[QuestionIngestDraft]:
    paragraphs = [p.text for p in doc.paragraphs if p.text and p.text.strip()]
    items = _answer_sheet_table_items(doc.tables)
    items.extend(_answer_sheet_paragraph_items(paragraphs))
    return _mcq_answer_grid_drafts(doc.tables) + _build_answer_drafts(items)


def ingest_question_docx(data: bytes) -> list[QuestionIngestDraft]:
    """Split paragraphs AND tables from an uploaded .docx into reviewable drafts."""
    if not data or not data[:4] == b"PK\x03\x04":
        raise ValueError("not a valid DOCX file")
    return _ingest_with_images(data, Document(BytesIO(data)))[0]