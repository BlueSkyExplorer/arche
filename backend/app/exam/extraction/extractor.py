"""Rule-based semantic extractor: DocumentBlock[] -> ExamDocument (deterministic).

Pipeline (each stage separable and testable):

1. numbering candidate detection (``numbering.py``) — "this looks like a label"
2. mark candidate detection (``marks.py``) — "this looks like a stated mark"
3. hierarchy reconciliation — build the QuestionNode tree at arbitrary depth
4. content accumulation — attach source blocks, preserving block identity
5. marks attachment — leaf -> ``own_marks``; non-leaf total -> ``declared_marks``

No LLM, no OCR, no DB models, no per-school special cases. This is the baseline
and fallback that the LLM extractor (ticket 04) shares the contract with.
"""

from __future__ import annotations

from typing import Any

from app.exam.extraction.content import (
    AMBIGUOUS_CONFIDENCE,
    MARK_ONLY,
    attach_marks,
    evidence,
    mark_evidence,
    to_content_block,
)
from app.exam.extraction.marks import detect_marks
from app.exam.extraction.numbering import (
    NumberingCandidate,
    NumberingPattern,
    detect_numbering,
)
from app.exam.ir import (
    AssetReference,
    ContentBlock,
    DeclaredMarkEvidence,
    ExamDocument,
    QuestionNode,
    Section,
)
from app.exam.parsing.blocks import BlockKind, DocumentBlock, ParseResult


def _canonical_rank(system: str, prefix: str, suffix: str) -> int:
    """Default depth hint for a numbering style (refined per-paper by observation).

    ``3 -> (b) -> (ii) -> (1)`` is the canonical nesting: arabic-dot (0) ->
    alpha (1) -> roman (2) -> arabic-paren (3). A paper that deviates (e.g. uses
    ``(1)`` directly under ``1.``) is surfaced as a level-jump warning.
    """
    if system == "arabic":
        return 3 if prefix == "(" else 0
    if system in ("alpha_lower", "alpha_upper"):
        return 1
    if system in ("roman_lower", "roman_upper"):
        return 2
    return 0


class RuleBasedExamExtractor:
    name = "rule-based"

    def extract(self, parsed: ParseResult) -> ExamDocument:
        sections: list[Section] = []
        section = Section()
        stack: list[tuple[int, QuestionNode]] = []
        current: QuestionNode | None = None
        all_nodes: list[QuestionNode] = []
        node_marks: dict[int, list[DeclaredMarkEvidence]] = {}
        warnings: list[dict[str, Any]] = []
        observed_patterns: list[NumberingPattern] = []
        last_value: dict[tuple[int, int], int] = {}
        referenced_assets: list[AssetReference] = []
        preamble: list[str] = []
        max_rank = -1

        def add_warning(code: str, message: str, block: DocumentBlock | None) -> None:
            warnings.append(
                {
                    "code": code,
                    "message": message,
                    "source_text": block.text if block is not None else None,
                    "page": block.page if block is not None else None,
                }
            )

        for block in parsed.blocks:
            if block.kind in (BlockKind.HEADER, BlockKind.FOOTER):
                continue
            if block.kind == BlockKind.HEADING:
                if section.questions or section.title is not None:
                    sections.append(section)
                section = Section(title=block.text, source=evidence(block))
                stack = []
                current = None
                last_value = {}
                max_rank = -1
                continue

            text = block.text or ""
            candidate = detect_numbering(text) if block.kind == BlockKind.TEXT else None

            if candidate is not None:
                node, rank = self._place(
                    candidate,
                    block,
                    section,
                    stack,
                    warnings,
                    observed_patterns,
                    last_value,
                    max_rank,
                )
                max_rank = max(max_rank, rank)
                all_nodes.append(node)
                current = node
                stem = text[candidate.end :].strip()
                if stem:
                    node.content.append(
                        ContentBlock(kind="paragraph", text=stem, source=evidence(block))
                    )
                    marks = detect_marks(stem)
                    if marks:
                        node_marks.setdefault(id(node), []).extend(
                            mark_evidence(m, block) for m in marks
                        )
                continue

            # content block (image / table / equation / caption / plain text)
            cb = to_content_block(block)
            if cb is None:
                continue
            marks = detect_marks(text)
            if block.kind == BlockKind.TEXT and MARK_ONLY.match(text) and marks:
                if current is not None:
                    node_marks.setdefault(id(current), []).extend(
                        mark_evidence(m, block) for m in marks
                    )
                else:
                    add_warning("mark_before_question", "mark token before any question", block)
                continue
            if current is not None:
                current.content.append(cb)
                if cb.asset is not None:
                    referenced_assets.append(cb.asset)
                if marks:
                    node_marks.setdefault(id(current), []).extend(
                        mark_evidence(m, block) for m in marks
                    )
            else:
                preamble.append(text)
                add_warning("content_before_question", "content block before any question", block)

        sections.append(section)

        for node in all_nodes:
            attach_marks(node, node_marks.get(id(node), []), warnings)

        meta: dict[str, Any] = {
            "extractor": self.name,
            "source_name": parsed.source_name,
            "format": parsed.format,
            "numbering_patterns": [p.as_dict() for p in observed_patterns],
            "extraction_warnings": warnings,
        }
        if preamble:
            meta["preamble_text"] = preamble

        return ExamDocument(sections=sections, assets=referenced_assets, meta=meta)

    def _place(
        self,
        candidate: NumberingCandidate,
        block: DocumentBlock,
        section: Section,
        stack: list[tuple[int, QuestionNode]],
        warnings: list[dict[str, Any]],
        observed_patterns: list[NumberingPattern],
        last_value: dict[tuple[int, int], int],
        max_rank: int,
    ) -> tuple[QuestionNode, int]:
        rank = _canonical_rank(candidate.system, candidate.prefix, candidate.suffix)
        pattern = NumberingPattern(candidate.system, candidate.prefix, candidate.suffix)
        if pattern not in observed_patterns:
            observed_patterns.append(pattern)

        node_warnings: list[dict[str, Any]] = []

        if rank > max_rank + 1:
            node_warnings.append(
                {
                    "code": "numbering_level_jump",
                    "message": f"'{candidate.token}' jumps from level {max_rank} to {rank}",
                    "source_text": block.text,
                    "page": block.page,
                }
            )

        # Return to a higher level: close every node at this rank or deeper.
        while stack and stack[-1][0] >= rank:
            stack.pop()
        parent = stack[-1][1] if stack else None

        node = QuestionNode(label=candidate.token, source=evidence(block))
        if parent is not None:
            parent.children.append(node)
        else:
            section.questions.append(node)
            if rank > 0:
                node_warnings.append(
                    {
                        "code": "orphan_numbering",
                        "message": f"'{candidate.token}' at level {rank} has no parent",
                        "source_text": block.text,
                        "page": block.page,
                    }
                )

        # Duplicate / non-monotonic numbering, scoped to the same parent level.
        parent_key = id(parent) if parent is not None else -1
        key = (parent_key, rank)
        if key in last_value and candidate.value <= last_value[key]:
            node_warnings.append(
                {
                    "code": "numbering_not_monotonic",
                    "message": (
                        f"'{candidate.token}' value {candidate.value} follows "
                        f"{last_value[key]} at the same level"
                    ),
                    "source_text": block.text,
                    "page": block.page,
                }
            )
        last_value[key] = candidate.value

        if node_warnings:
            node.confidence = AMBIGUOUS_CONFIDENCE
            warnings.extend(node_warnings)

        stack.append((rank, node))
        return node, rank
