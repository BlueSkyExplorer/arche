"""Deterministic Exam IR materialization.

Turns a validated ``ExamDocument`` into the existing ingest representation
(``QuestionIngestDraft``). This layer does *no* semantic interpretation: it
never re-detects numbering or marks, never re-parses the source, never calls an
LLM or network, and never knows which extractor produced the document.

``ExamDocument -> QuestionIngestDraft`` is the pure translation; the existing
``QuestionIngestDraft -> QuestionCreate -> Question`` path handles persistence.
Image assets are resolved through an injectable ``asset_id_for`` callback (the
caller persists bytes -> UUID); without it, image blocks are flagged
``needs_review`` rather than silently dropped.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal, cast
from uuid import UUID

from app.exam.ir import ContentBlock, ExamDocument, QuestionNode
from app.exam.validation import validate_exam_document
from app.schemas.content import (
    BlockNode,
    DocNode,
    HeadingAttrs,
    HeadingNode,
    ImageAttrs,
    ImageNode,
    ParagraphNode,
    SubQuestionAttrs,
    SubQuestionNode,
    TableCellNode,
    TableNode,
    TableRowNode,
    TextNode,
)
from app.schemas.question import DeclaredMark, QuestionIngestDraft

AssetResolver = Callable[[str], UUID]
HeadingLevel = Literal[1, 2, 3]


def _clamp_heading_level(level: int | None) -> HeadingLevel:
    # content_json heading levels are 1..3; the IR allows 1..6
    return cast(HeadingLevel, min(max(level or 1, 1), 3))


def _text_node(text: str) -> TextNode:
    return TextNode(type="text", text=text)


def _paragraph(text: str) -> ParagraphNode:
    return ParagraphNode(type="paragraph", content=[_text_node(text)])


def _block_node(
    block: ContentBlock,
    asset_id_for: AssetResolver | None,
    unresolved: set[str],
) -> BlockNode | None:
    kind = block.kind
    if kind == "image":
        if block.asset is None:
            return None
        local_id = block.asset.local_id
        if asset_id_for is None:
            unresolved.add(local_id)
            return None
        return ImageNode(
            type="image", attrs=ImageAttrs(asset_id=asset_id_for(local_id))
        )
    if kind == "heading":
        return HeadingNode(
            type="heading",
            attrs=HeadingAttrs(level=_clamp_heading_level(block.heading_level)),
            content=[_text_node(block.text or "")],
        )
    if kind == "table":
        rows = block.rows or []
        return TableNode(
            type="table",
            content=[
                TableRowNode(
                    type="tableRow",
                    content=[
                        TableCellNode(
                            type="tableCell", content=[_paragraph(cell or "")]
                        )
                        for cell in row
                    ],
                )
                for row in rows
            ],
        )
    # equation / list / answer_space have no exact content_json node: preserve the
    # text as a paragraph (documented lossy mapping — see ADR-0008).
    return _paragraph(block.text or "")


def _sub_question(
    node: QuestionNode,
    asset_id_for: AssetResolver | None,
    unresolved: set[str],
) -> SubQuestionNode:
    blocks: list[BlockNode] = []
    for block in node.content:
        mapped = _block_node(block, asset_id_for, unresolved)
        if mapped is not None:
            blocks.append(mapped)
    for child in node.children:
        blocks.append(_sub_question(child, asset_id_for, unresolved))
    if not blocks:  # SubQuestionNode requires >=1 content block
        blocks.append(_paragraph(""))
    return SubQuestionNode(
        type="subQuestion",
        attrs=SubQuestionAttrs(label=node.label, marks=node.own_marks),
        content=blocks,
    )


def _doc_node(
    node: QuestionNode,
    asset_id_for: AssetResolver | None,
    unresolved: set[str],
) -> DocNode:
    blocks: list[BlockNode] = []
    for block in node.content:
        mapped = _block_node(block, asset_id_for, unresolved)
        if mapped is not None:
            blocks.append(mapped)
    for child in node.children:
        blocks.append(_sub_question(child, asset_id_for, unresolved))
    return DocNode(marks=node.own_marks, content=blocks)


def _collect_declared(node: QuestionNode, location: str = "") -> list[DeclaredMark]:
    out = [
        DeclaredMark(value=m.value, raw_text=m.raw_text, location=location)
        for m in node.declared_marks
    ]
    for child in node.children:
        out.extend(_collect_declared(child, location + (child.label or "")))
    return out


def materialize_exam_document(
    document: ExamDocument,
    *,
    asset_id_for: AssetResolver | None = None,
) -> list[QuestionIngestDraft]:
    """Translate a validated ExamDocument into reviewable ingest drafts.

    One draft per top-level question. ``marks`` mirrors the leaf-only invariant:
    a known leaf's ``own_marks`` is carried through, an unknown leaf stays
    ``None`` (never 0), and a non-leaf's marks are computed from its leaves (so
    the draft's own ``marks`` field is ``None``).
    """
    report = validate_exam_document(document)

    drafts: list[QuestionIngestDraft] = []
    question_index = 0
    for section_index, section in enumerate(document.sections):
        section_path = section.title or f"Section {section_index + 1}"
        for node in section.questions:
            question_index += 1
            unresolved: set[str] = set()
            content = _doc_node(node, asset_id_for, unresolved)

            question_path = f"{section_path}/{node.label or '?'}"
            own_issues = [
                issue
                for issue in report.issues
                if issue.location == question_path
                or issue.location.startswith(question_path + "/")
            ]
            validation_issues = [f"{i.code}: {i.message}" for i in own_issues]
            if unresolved:
                validation_issues.append(
                    f"unresolved_image_asset: {', '.join(sorted(unresolved))}"
                )
            needs_review = (
                any(i.severity in ("warning", "blocking") for i in own_issues)
                or bool(unresolved)
            )

            drafts.append(
                QuestionIngestDraft(
                    internal_title=node.label or f"Question {question_index}",
                    subject=document.subject or "",
                    level=document.level or "",
                    tags_json=[],
                    source_note=section.title or None,
                    content_json=content,
                    marks=node.own_marks,
                    declared_marks=_collect_declared(node),
                    needs_review=needs_review,
                    validation_issues=validation_issues,
                    status="draft",
                )
            )
    return drafts
