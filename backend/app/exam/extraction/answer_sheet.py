"""Deterministic answer-sheet extractor (答案卷 → 題號→答案+分數 tree).

Handles the two real ``.doc`` answer-key formats from 余振強紀念中學 (biology):

- **table format** (20260515 C ANS): each structured question is a DOCX table with
  columns ``[題號, 子題, 子子題, 答案, 分數]``; the label columns are forward-filled
  across vertically-merged cells.
- **text format** (Sample C ANS): loose text lines with ``Q1.`` / ``(a)`` / ``(i)``
  labels (including fused ``Q3a`` and bare ``b``) and trailing marks ``(1分)``.

Lossless-first: cell paragraphs/line-breaks are preserved (never flattened for
display), non-text content (images/diagrams) is flagged — never turned into
garbled text — and the section's *declared* total is kept separate from the
*computed* leaf-mark total, with a mismatch warning when they differ.

Output is a provider-independent tree (``AnsSheet`` / ``AnsSection`` /
``AnsNode``). Not wired into Question Library yet — review-only extraction MVP.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal

from app.exam.parsing.blocks import BlockKind, DocumentBlock, ParseResult

# --- data model -------------------------------------------------------------


@dataclass
class AnsNode:
    """One question / sub-part. Leaf holds the answer text + authoritative marks.

    ``answer`` is a list of source lines (cell paragraphs preserved verbatim,
    split on ``\\n``). ``has_non_text_content`` is True when the node contains an
    image / diagram the extractor cannot reliably turn into text (never faked).
    """

    label: str | None
    answer: list[str] = field(default_factory=list)
    marks: Decimal | None = None
    children: list[AnsNode] = field(default_factory=list)
    has_non_text_content: bool = False

    def total(self) -> Decimal | None:
        if not self.children:
            return self.marks
        vals = [c.total() for c in self.children]
        if any(v is None for v in vals):
            return None
        return sum((v for v in vals if v is not None), Decimal(0))

    def any_non_text(self) -> bool:
        """True if this node or any descendant carries non-text content."""
        return self.has_non_text_content or any(c.any_non_text() for c in self.children)


@dataclass
class AnsSection:
    """One section (甲部/乙部…). ``declared_total`` is what the header states
    (e.g. ``(50分)``); ``computed_total`` is the sum of extracted leaf marks —
    kept separate so a discrepancy is visible, never papered over."""

    title: str
    declared_total: Decimal | None = None
    mcq: list[tuple[str, str]] | None = None
    questions: list[AnsNode] = field(default_factory=list)
    # non-text content NOT attached to any question (e.g. a detached image block)
    standalone_non_text: bool = False

    @property
    def has_non_text_content(self) -> bool:
        """Derived from descendant nodes + standalone evidence, so a node flagged
        non-text can never be missed at the section level."""
        return self.standalone_non_text or any(q.any_non_text() for q in self.questions)

    def computed_total(self) -> Decimal | None:
        """Sum of extracted leaf marks (structured questions only; MCQ excluded)."""
        if not self.questions:
            return None
        vals = [q.total() for q in self.questions]
        if any(v is None for v in vals):
            return None
        return sum((v for v in vals if v is not None), Decimal(0))


@dataclass
class AnsWarning:
    """A typed extraction/validation warning — the extraction → API/Review UI contract."""

    code: str
    message: str
    section: str | None = None
    path: str | None = None
    declared: Decimal | None = None
    computed: Decimal | None = None


@dataclass
class AnsSheet:
    title: str
    sections: list[AnsSection] = field(default_factory=list)
    warnings: list[AnsWarning] = field(default_factory=list)
    # raster-image asset references (local_id -> mime) found in the source
    asset_refs: list[dict] = field(default_factory=list)


# --- marks ------------------------------------------------------------------

_MARK_PAREN = re.compile(
    r"[(（]\s*(\d+(?:\.\d+)?)\s*分\s*[)）](?:\s*[x×]\s*(\d+))?"
)
_MARK_COMMA = re.compile(r"[(（][^()（）]*[，,]\s*(\d+(?:\.\d+)?)\s*[)）]")
_MARK_PAREN_NUM = re.compile(r"[(（]\s*(\d+(?:\.\d+)?)\s*[)）]")
# bare "N分" outside parentheses, but NOT a clock time (e.g. "1時30分").
_MARK_BARE = re.compile(r"(?<!時)(?<!點)(?<![\d.])(\d+(?:\.\d+)?)\s*分")
_PAREN_ANY = re.compile(r"[(（][^()（）]*[)）]")


def parse_marks(text: str) -> Decimal | None:
    """Sum every mark token in ``text``; ``None`` if none present.

    Counts ``(1分)``, ``(1分)x3``, ``(2分)``, ``(1)``, ``(其中一項，1)`` and bare
    ``1分``; ignores per-item hints like ``(每項1分)`` and clock times like
    ``1時30分``.
    """
    total = Decimal(0)
    found = False
    for m in _MARK_PAREN.finditer(text):
        found = True
        total += Decimal(m.group(1)) * (int(m.group(2)) if m.group(2) else 1)
    for m in _MARK_COMMA.finditer(text):
        found = True
        total += Decimal(m.group(1))
    for m in _MARK_PAREN_NUM.finditer(text):
        found = True
        total += Decimal(m.group(1))
    stripped = _PAREN_ANY.sub(" ", text)
    for m in _MARK_BARE.finditer(stripped):
        found = True
        total += Decimal(m.group(1))
    return total if found else None


def strip_marks(text: str) -> str:
    s = _MARK_PAREN.sub(" ", text)
    s = _MARK_COMMA.sub(" ", s)
    s = _MARK_PAREN_NUM.sub(" ", s)
    s = re.sub(r"[(（][^()（）]*分[^()（）]*[)）]", " ", s)  # (每項1分) hints
    s = _MARK_BARE.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


# --- labels -----------------------------------------------------------------

_QUESTION = re.compile(r"^[Qq]\s*(\d+)\s*[.)、．）]?")
_PAREN_LABEL = re.compile(r"^[(（]\s*([A-Za-z0-9]+)\s*[)）]")
_BARE_LETTER = re.compile(r"^([a-z])\s*(?![A-Za-z0-9_])")
_ROMAN = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}


def leading_labels(line: str) -> tuple[list[str], str]:
    """Split a leading label sequence off a text line -> (labels, rest)."""
    s = line.lstrip()
    labels: list[str] = []
    m = _QUESTION.match(s)
    if m:
        labels.append(f"Q{m.group(1)}")
        s = s[m.end():].lstrip()
        fused = _BARE_LETTER.match(s)
        if fused and not s.startswith(("(", "（")):
            labels.append(fused.group(1))
            s = s[fused.end():].lstrip()
    while True:
        m = _PAREN_LABEL.match(s)
        if not m:
            break
        labels.append(f"({m.group(1).lower()})")
        s = s[m.end():].lstrip()
    if not labels:
        m = _BARE_LETTER.match(s)
        if m:
            labels.append(m.group(1))
            s = s[m.end():].lstrip()
    return labels, s.strip()


def label_rank(label: str) -> int:
    """Depth: question(0) -> alpha sub(1) -> roman sub-sub(2)."""
    if label.startswith("Q"):
        return 0
    if label.startswith("("):
        inner = label[1:-1]
        if inner in _ROMAN:
            return 2
        return 1
    return 1  # bare letter


# --- MCQ grid ---------------------------------------------------------------


def parse_mcq(table: DocumentBlock) -> list[tuple[str, str]] | None:
    """A 題號/答案 grid (2 column-pairs) -> [(num, answer), ...]; None if not MCQ."""
    rows = table.rows or []
    if not rows:
        return None
    if "題號" not in "".join(rows[0]) or "答案" not in "".join(rows[0]):
        return None
    out: list[tuple[str, str]] = []
    for r in rows[1:]:
        for i in range(0, len(r) - 1, 2):
            num, ans = (r[i] or "").strip(), (r[i + 1] or "").strip()
            if num.isdigit() and ans:
                out.append((num, ans))
    return out or None


# --- table format (20260515) ------------------------------------------------

Leaf = tuple[list[str], list[str], Decimal | None, bool]  # (path, lines, marks, non_text)


def _is_question_table(table: DocumentBlock) -> bool:
    first = (table.rows[0][0] if table.rows and table.rows[0] else "").strip()
    return bool(re.match(r"^[Qq]\s*\d|\d+\s*[.)、．]?", first))


def parse_question_table(table: DocumentBlock) -> tuple[str, list[Leaf]] | None:
    """One question table -> (question_label, leaves); leaf = (sub_path, lines, marks, non_text)."""
    rows = table.rows or []
    if not rows or not _is_question_table(table):
        return None
    non_text_cells: dict[str, str] = table.meta.get("non_text_cells", {})
    q_label: str | None = None
    cur_sub: str | None = None
    cur_subsub: str | None = None
    leaves: list[Leaf] = []
    for r_idx, row in enumerate(rows):
        cells = list(row) + ["", "", "", "", ""]
        cq = (cells[0] or "").strip()
        ca = (cells[1] or "").strip()
        ci = (cells[2] or "").strip()
        content = (cells[3] or "").strip()
        marks_s = (cells[4] or "").strip()
        if cq:
            q_label = cq
            cur_sub = None
            cur_subsub = None
        if ca:
            cur_sub = ca
            cur_subsub = None
        if ci:
            cur_subsub = ci
        path = [p for p in (cur_sub, cur_subsub) if p]
        lines = [ln.strip() for ln in content.split("\n")] if content else []
        lines = [ln for ln in lines if ln]
        marks = parse_marks(marks_s)
        non_text = f"{r_idx}:3" in non_text_cells
        if lines or marks is not None or non_text:
            leaves.append((path, lines, marks, non_text))
    if q_label is None:
        return None
    return q_label, leaves


def _build_tree(q_label: str, leaves: list[Leaf]) -> AnsNode:
    root = AnsNode(label=q_label)
    for path, lines, marks, non_text in leaves:
        node = root
        for lbl in path:
            child = next((c for c in node.children if c.label == lbl), None)
            if child is None:
                child = AnsNode(label=lbl)
                node.children.append(child)
            node = child
        node.answer.extend(lines)
        if marks is not None:
            node.marks = marks
        if non_text:
            node.has_non_text_content = True
    return root


# --- text format (Sample C) -------------------------------------------------


def _text_to_tree(blocks: list[DocumentBlock]) -> list[AnsNode]:
    roots: list[AnsNode] = []
    stack: list[tuple[int, AnsNode]] = []  # (rank, node)
    for block in blocks:
        if block.kind in (BlockKind.HEADER, BlockKind.FOOTER):
            continue
        if block.kind != BlockKind.TEXT:
            if block.kind == BlockKind.TABLE and stack:
                non_text = block.meta.get("non_text_cells", {})
                for r_idx, r in enumerate(block.rows or []):
                    cells: list[str] = []
                    for c_idx, c in enumerate(r):
                        if f"{r_idx}:{c_idx}" in non_text:
                            cells.append("[圖]")
                            stack[-1][1].has_non_text_content = True
                        else:
                            cells.append(c or "")
                    stack[-1][1].answer.append(" | ".join(cells))
            elif block.kind == BlockKind.IMAGE and stack:
                stack[-1][1].has_non_text_content = True
            continue
        text = block.text or ""
        labels, rest = leading_labels(text)
        if not labels:
            if stack:
                node = stack[-1][1]
                if rest:
                    node.answer.append(strip_marks(rest))
                m = parse_marks(rest)
                if m is not None:
                    node.marks = (node.marks or Decimal(0)) + m
            continue
        marks = parse_marks(rest)
        clean = strip_marks(rest)
        for idx, lbl in enumerate(labels):
            rank = label_rank(lbl)
            while stack and stack[-1][0] >= rank:
                stack.pop()
            node = AnsNode(label=lbl)
            if idx == len(labels) - 1:
                if clean:
                    node.answer.append(clean)
                if marks is not None:
                    node.marks = marks
            if stack:
                stack[-1][1].children.append(node)
            else:
                roots.append(node)
            stack.append((rank, node))
    return roots


# --- top-level --------------------------------------------------------------

_DECLARED_TOTAL = re.compile(r"[（(]\s*(\d+(?:\.\d+)?)\s*分\s*[)）]")


def extract_answer_sheet(parsed: ParseResult) -> AnsSheet:
    preamble: list[str] = []
    heading: str | None = None
    cur_blocks: list[DocumentBlock] = []
    raw_sections: list[tuple[str, list[DocumentBlock]]] = []

    for block in parsed.blocks:
        if block.kind == BlockKind.TEXT:
            t = (block.text or "").strip()
            if re.match(r"^[甲乙丙丁戊己]部", t):
                if heading is not None:
                    raw_sections.append((heading, cur_blocks))
                heading = t
                cur_blocks = []
                continue
            if heading is None:
                preamble.append(t)
                continue
        cur_blocks.append(block)
    if heading is not None:
        raw_sections.append((heading, cur_blocks))

    sheet = AnsSheet(title=" ".join(p for p in preamble if p))
    for heading, blocks in raw_sections:
        sec = AnsSection(title=heading)
        m = _DECLARED_TOTAL.search(heading)
        if m:
            sec.declared_total = Decimal(m.group(1))
        if "多項選擇" in heading or heading.startswith("甲"):
            for b in blocks:
                if b.kind == BlockKind.TABLE:
                    mcq = parse_mcq(b)
                    if mcq:
                        sec.mcq = mcq
                        break
        else:
            tables = [b for b in blocks if b.kind == BlockKind.TABLE and _is_question_table(b)]
            if tables:
                for b in blocks:
                    if b.kind == BlockKind.TABLE:
                        parsed_q = parse_question_table(b)
                        if parsed_q:
                            q_label, leaves = parsed_q
                            sec.questions.append(_build_tree(q_label, leaves))
            else:
                sec.questions = _text_to_tree(blocks)
            # standalone non-text evidence not attached to any question node
            # (question-cell diagrams are already flagged on the nodes themselves)
            sec.standalone_non_text = any(
                b.kind == BlockKind.IMAGE
                or (
                    b.kind == BlockKind.TABLE
                    and not _is_question_table(b)
                    and b.meta.get("non_text_cells")
                )
                for b in blocks
            )

        sheet.sections.append(sec)

    # raster-image asset references (for preview / persistence)
    for b in parsed.blocks:
        if b.kind == BlockKind.IMAGE and b.asset is not None:
            sheet.asset_refs.append(
                {"local_id": b.asset.local_id, "mime_type": b.asset.mime_type}
            )

    compute_warnings(sheet)
    return sheet


def compute_warnings(sheet: AnsSheet) -> None:
    """(Re)compute ``sheet.warnings`` from the sections.

    Keeps the declared total and the computed leaf-mark total separate and flags
    a mismatch — never fudging leaf marks to match the declared total. Also
    flags sections with non-text content. Called after extraction and again
    after human review so the warnings always reflect the current data.
    """
    sheet.warnings = []
    for sec in sheet.sections:
        computed = sec.computed_total()
        if (
            sec.declared_total is not None
            and computed is not None
            and sec.declared_total != computed
        ):
            sheet.warnings.append(
                AnsWarning(
                    code="declared_total_mismatch",
                    message=(
                        f"declares {sec.declared_total} marks but extracted leaf "
                        f"marks sum to {computed}"
                    ),
                    section=sec.title,
                    declared=sec.declared_total,
                    computed=computed,
                )
            )
        if sec.has_non_text_content:
            sheet.warnings.append(
                AnsWarning(
                    code="non_text_content",
                    message="contains image/diagram content that was not extracted "
                    "as text (no OCR)",
                    section=sec.title,
                )
            )


# --- render -----------------------------------------------------------------


def render(sheet: AnsSheet) -> str:
    lines: list[str] = [sheet.title, ""]
    for sec in sheet.sections:
        header = f"## {sec.title}"
        if sec.declared_total is not None:
            computed = sec.computed_total()
            if computed is not None and computed != sec.declared_total:
                header += f"  ⚠ 宣稱 {sec.declared_total}分 / 實計 {computed}分"
        lines.append(header)
        if sec.mcq:
            lines.append(f"  多項選擇 (MCQ) {len(sec.mcq)} 題:")
            lines.append("  " + "  ".join(f"{n}.{a}" for n, a in sec.mcq))
            lines.append("")

        def walk(node: AnsNode, depth: int) -> None:
            indent = "  " * depth
            if node.children:
                total = node.total()
                t = f" = {total}分" if total is not None else ""
                lines.append(f"{indent}{node.label}{t}")
                for c in node.children:
                    walk(c, depth + 1)
            else:
                m = f" = {node.marks}分" if node.marks is not None else " = ?分"
                flag = "  ⚠[圖]" if node.has_non_text_content else ""
                lines.append(f"{indent}{node.label}{m}{flag}")
                for a in node.answer:
                    lines.append(f"{indent}    ↳ {a}")

        for q in sec.questions:
            walk(q, 1)
        lines.append("")
    if sheet.warnings:
        lines.append("## 驗證問題")
        for w in sheet.warnings:
            lines.append(f"  - [{w.code}] {w.message}")
    return "\n".join(lines)


# --- JSON serialization (for durable persistence / API) ---------------------


def _dec(v: Decimal | None) -> str | None:
    return str(v) if v is not None else None


def _to_dec(v: object) -> Decimal | None:
    if v is None or v == "":
        return None
    return Decimal(str(v))


def node_to_dict(node: AnsNode) -> dict:
    return {
        "label": node.label,
        "answer": list(node.answer),
        "marks": _dec(node.marks),
        "children": [node_to_dict(c) for c in node.children],
        "has_non_text_content": node.has_non_text_content,
    }


def node_from_dict(d: dict) -> AnsNode:
    return AnsNode(
        label=d.get("label"),
        answer=[str(a) for a in d.get("answer", [])],
        marks=_to_dec(d.get("marks")),
        children=[node_from_dict(c) for c in d.get("children", [])],
        has_non_text_content=bool(d.get("has_non_text_content", False)),
    )


def warning_to_dict(w: AnsWarning) -> dict:
    return {
        "code": w.code,
        "message": w.message,
        "section": w.section,
        "path": w.path,
        "declared": _dec(w.declared),
        "computed": _dec(w.computed),
    }


def warning_from_dict(d: dict) -> AnsWarning:
    return AnsWarning(
        code=str(d.get("code", "")),
        message=str(d.get("message", "")),
        section=d.get("section"),
        path=d.get("path"),
        declared=_to_dec(d.get("declared")),
        computed=_to_dec(d.get("computed")),
    )


def section_to_dict(sec: AnsSection) -> dict:
    return {
        "title": sec.title,
        "declared_total": _dec(sec.declared_total),
        "computed_total": _dec(sec.computed_total()),
        "mcq": sec.mcq,
        "questions": [node_to_dict(q) for q in sec.questions],
        "standalone_non_text": sec.standalone_non_text,
    }


def section_from_dict(d: dict) -> AnsSection:
    mcq = d.get("mcq")
    return AnsSection(
        title=str(d.get("title", "")),
        declared_total=_to_dec(d.get("declared_total")),
        mcq=[(str(n), str(a)) for n, a in mcq] if mcq else None,
        questions=[node_from_dict(q) for q in d.get("questions", [])],
        standalone_non_text=bool(d.get("standalone_non_text", False)),
    )


def sheet_to_dict(sheet: AnsSheet) -> dict:
    return {
        "title": sheet.title,
        "sections": [section_to_dict(s) for s in sheet.sections],
        "warnings": [warning_to_dict(w) for w in sheet.warnings],
        "asset_refs": list(sheet.asset_refs),
    }


def sheet_from_dict(d: dict) -> AnsSheet:
    return AnsSheet(
        title=str(d.get("title", "")),
        sections=[section_from_dict(s) for s in d.get("sections", [])],
        warnings=[warning_from_dict(w) for w in d.get("warnings", [])],
        asset_refs=list(d.get("asset_refs", [])),
    )
