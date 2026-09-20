"""Shared deterministic helpers for building Exam IR content from DocumentBlock[].

Both the rule-based extractor and the LLM assembler use these, so block→content
mapping, mark detection, and mark attachment are defined exactly once.
"""

from __future__ import annotations

import re
from typing import Any

from app.exam.extraction.marks import MarkCandidate
from app.exam.ir import (
    ContentBlock,
    DeclaredMarkEvidence,
    QuestionNode,
    SourceEvidence,
)
from app.exam.parsing.blocks import BlockKind, DocumentBlock

# Below validation's LOW_CONFIDENCE_THRESHOLD (0.5): an ambiguous placement is
# surfaced as "low confidence -> needs_review" rather than silently accepted.
AMBIGUOUS_CONFIDENCE = 0.4

# A block that is *only* a mark token (no other text) — e.g. "(3 marks)" on its
# own line. It is recorded as mark evidence, not as question content.
MARK_ONLY = re.compile(
    r"^\s*(?:"
    r"\(\s*\d+(?:\.\d+)?\s*marks?\s*\)"
    r"|\[\s*\d+(?:\.\d+)?\s*marks?\s*\]"
    r"|\d+(?:\.\d+)?\s*marks?"
    r"|[（(]\s*\d+(?:\.\d+)?\s*分\s*[）)]"
    r"|\d+(?:\.\d+)?\s*分"
    r")\s*$",
    re.IGNORECASE,
)


def evidence(block: DocumentBlock) -> SourceEvidence:
    return SourceEvidence(
        page=block.page,
        block_id=block.id,
        bbox=block.bbox,
        source_text=block.text or "",
        confidence=block.confidence if block.confidence is not None else 1.0,
    )


def to_content_block(block: DocumentBlock) -> ContentBlock | None:
    ev = evidence(block)
    if block.kind == BlockKind.IMAGE:
        return ContentBlock(kind="image", asset=block.asset, source=ev)
    if block.kind == BlockKind.TABLE:
        return ContentBlock(kind="table", rows=block.rows, source=ev)
    if block.kind == BlockKind.EQUATION:
        return ContentBlock(kind="equation", text=block.text, source=ev)
    if block.kind == BlockKind.HEADING:
        return ContentBlock(
            kind="heading", text=block.text, heading_level=block.meta.get("level"), source=ev
        )
    if block.kind == BlockKind.CAPTION:
        return ContentBlock(kind="caption", text=block.text, source=ev)
    # TEXT becomes a paragraph.
    return ContentBlock(kind="paragraph", text=block.text, source=ev)


def mark_evidence(mark: MarkCandidate, block: DocumentBlock) -> DeclaredMarkEvidence:
    ev = evidence(block)
    return DeclaredMarkEvidence(
        value=mark.value,
        raw_text=mark.raw_text,
        source=SourceEvidence(
            page=ev.page, block_id=ev.block_id, bbox=ev.bbox, source_text=mark.raw_text
        ),
    )


def attach_marks(
    node: QuestionNode, marks: list[DeclaredMarkEvidence], warnings: list[dict[str, Any]]
) -> None:
    """Leaf -> ``own_marks``; non-leaf total -> ``declared_marks`` (evidence only).

    Unknown stays ``None`` (never 0). Multiple candidates on one leaf are
    ambiguous -> ``None`` + warning. The final invariants are enforced by the
    deterministic validator, not here.
    """
    if not marks:
        return  # leaf keeps own_marks=None (unknown) — validation flags it
    node.declared_marks = marks
    if node.children:
        node.own_marks = None
    elif len(marks) == 1:
        node.own_marks = marks[0].value
    else:
        node.own_marks = None
        node.confidence = AMBIGUOUS_CONFIDENCE
        warnings.append(
            {
                "code": "ambiguous_marks",
                "message": f"leaf '{node.label}' has {len(marks)} mark candidates",
                "source_text": "; ".join(m.raw_text for m in marks),
                "page": None,
            }
        )
