"""Deterministic assembler: SemanticExtractionResult + DocumentBlock[] -> ExamDocument.

The LLM only decides *structure* (sections, parent/child, labels, confidence).
Everything else — content mapping, mark detection, evidence, and the final
invariants — is deterministic and reuses the same helpers as the rule-based
extractor.

Block references are validated here. A block claimed by two nodes is
deduplicated deterministically (the deepest — most specific — claiming node
wins; later claims drop the block and are warned), so a block is never
authoritatively assigned twice. Labels for numbered questions are reconciled
deterministically: the numbering detector's token on a node's first owned text
block is authoritative — the LLM cannot null out (or rename) a label the
detector already found. The LLM's ``label`` is only a fallback for genuinely
unnumbered / ambiguous nodes.
"""

from __future__ import annotations

from collections import Counter
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
from app.exam.extraction.numbering import detect_numbering
from app.exam.extraction.semantic import (
    SemanticExtractionResult,
    SemanticNodeDTO,
)
from app.exam.ir import AssetReference, ExamDocument, QuestionNode, Section, SourceEvidence
from app.exam.parsing.blocks import BlockKind, DocumentBlock, ParseResult


def assemble(
    result: SemanticExtractionResult, parsed: ParseResult, warnings: list[dict[str, Any]]
) -> ExamDocument:
    blocks: dict[str, DocumentBlock] = {b.id: b for b in parsed.blocks}
    node_by_id: dict[str, SemanticNodeDTO] = {d.id: d for d in result.nodes}
    assets: list[AssetReference] = []

    id_counts = Counter(d.id for d in result.nodes)
    for dto in result.nodes:
        if id_counts[dto.id] > 1:
            warnings.append(
                {
                    "code": "duplicate_node_id",
                    "message": f"node id '{dto.id}' appears {id_counts[dto.id]} times",
                    "source_text": None,
                    "page": None,
                }
            )
        if dto.parent_id is not None and dto.parent_id not in node_by_id:
            warnings.append(
                {
                    "code": "unknown_parent_id",
                    "message": f"node '{dto.id}' has unknown parent '{dto.parent_id}'",
                    "source_text": None,
                    "page": None,
                }
            )

    # Node depth (number of ancestors) — used to resolve block-ownership ties in
    # favour of the most specific (deepest) node, so a parent that over-claims a
    # child's block never starves the child.
    depth: dict[str, int] = {}
    for dto in result.nodes:
        d = 0
        seen: set[str] = set()
        cur = dto
        while cur.parent_id is not None and cur.parent_id in node_by_id and cur.id not in seen:
            seen.add(cur.id)
            cur = node_by_id[cur.parent_id]
            d += 1
        depth[dto.id] = d

    # Exclusive block ownership: a block belongs to exactly one node. When two
    # nodes claim it, the deepest (most specific) wins; ties go to emission order.
    owner: dict[str, str] = {}
    for dto in result.nodes:
        for bid in dto.content_block_ids:
            if bid not in blocks:
                continue
            existing = owner.get(bid)
            if existing is None or depth[dto.id] > depth[existing]:
                owner[bid] = dto.id

    # Deterministic numbering label per text block (authoritative for labels).
    block_label: dict[str, str] = {}
    for bid, block in blocks.items():
        if block.kind == BlockKind.TEXT:
            candidate = detect_numbering(block.text or "")
            if candidate is not None:
                block_label[bid] = candidate.token

    children: dict[str | None, list[SemanticNodeDTO]] = {}
    for dto in result.nodes:
        pid = dto.parent_id if dto.parent_id in node_by_id else None
        children.setdefault(pid, []).append(dto)

    def ordered_blocks(dto: SemanticNodeDTO) -> list[str]:
        return sorted(
            dto.content_block_ids,
            key=lambda i: blocks[i].order if i in blocks else 1 << 30,
        )

    def build_content(
        dto: SemanticNodeDTO,
    ) -> tuple[list, list, DocumentBlock | None, bool]:
        content: list = []
        marks: list = []
        first_block: DocumentBlock | None = None
        had_unknown = False
        for bid in ordered_blocks(dto):
            if bid not in blocks:
                had_unknown = True
                warnings.append(
                    {
                        "code": "unknown_block_id",
                        "message": f"node '{dto.id}' references unknown block '{bid}'",
                        "source_text": None,
                        "page": None,
                    }
                )
                continue
            if owner.get(bid) != dto.id:
                # deterministic dedup: the block belongs to an earlier node
                warnings.append(
                    {
                        "code": "duplicate_block_assignment",
                        "message": f"block '{bid}' assigned to '{dto.id}' and '{owner[bid]}'",
                        "source_text": None,
                        "page": None,
                    }
                )
                continue
            block = blocks[bid]
            if first_block is None:
                first_block = block
            text = block.text or ""
            found_marks = detect_marks(text)
            if block.kind == BlockKind.TEXT and MARK_ONLY.match(text) and found_marks:
                marks.extend(mark_evidence(m, block) for m in found_marks)
                continue
            cb = to_content_block(block)
            if cb is None:
                continue
            content.append(cb)
            if cb.asset is not None:
                assets.append(cb.asset)
            if found_marks:
                marks.extend(mark_evidence(m, block) for m in found_marks)
        return content, marks, first_block, had_unknown

    def deterministic_label(dto: SemanticNodeDTO) -> str | None:
        for bid in ordered_blocks(dto):
            if bid in block_label and owner.get(bid) == dto.id:
                return block_label[bid]
        return None

    def assemble_node(dto: SemanticNodeDTO, visiting: set[str]) -> QuestionNode:
        if dto.id in visiting:
            warnings.append(
                {
                    "code": "node_cycle",
                    "message": f"cycle detected at node '{dto.id}'",
                    "source_text": None,
                    "page": None,
                }
            )
            return QuestionNode(label=dto.label)
        visiting.add(dto.id)
        content, marks, first_block, had_unknown = build_content(dto)
        det_label = deterministic_label(dto)
        node = QuestionNode(
            label=det_label if det_label is not None else dto.label,
            confidence=dto.confidence,
            content=content,
            source=evidence(first_block) if first_block is not None else SourceEvidence(),
        )
        if had_unknown:
            node.confidence = min(node.confidence, AMBIGUOUS_CONFIDENCE)
        for child in children.get(dto.id, []):
            node.children.append(assemble_node(child, visiting))
        visiting.discard(dto.id)
        attach_marks(node, marks, warnings)
        return node

    sections: list[Section] = []
    referenced_node_ids: set[str] = set()

    for sec_dto in result.sections:
        heading_block = None
        if sec_dto.heading_block_id is not None:
            if sec_dto.heading_block_id in blocks:
                heading_block = blocks[sec_dto.heading_block_id]
            else:
                warnings.append(
                    {
                        "code": "unknown_block_id",
                        "message": (
                            f"section references unknown heading block "
                            f"'{sec_dto.heading_block_id}'"
                        ),
                        "source_text": None,
                        "page": None,
                    }
                )
        section = Section(
            title=heading_block.text if heading_block is not None else None,
            source=evidence(heading_block) if heading_block is not None else SourceEvidence(),
        )
        for nid in sec_dto.node_ids:
            if nid not in node_by_id:
                warnings.append(
                    {
                        "code": "unknown_node_id",
                        "message": f"section references unknown node '{nid}'",
                        "source_text": None,
                        "page": None,
                    }
                )
                continue
            referenced_node_ids.add(nid)
            section.questions.append(assemble_node(node_by_id[nid], set()))
        sections.append(section)

    # Any top-level node not claimed by a section lands in a default section.
    orphans = [d for d in result.nodes if d.parent_id is None and d.id not in referenced_node_ids]
    if orphans:
        warnings.append(
            {
                "code": "unclaimed_node",
                "message": f"{len(orphans)} top-level node(s) not in any section",
                "source_text": None,
                "page": None,
            }
        )
        sections.append(
            Section(questions=[assemble_node(d, set()) for d in orphans])
        )
    if not sections:
        sections.append(
            Section(
                questions=[assemble_node(d, set()) for d in children.get(None, [])]
            )
        )

    # Prune nodes emptied by dedup (and drop empty untitled sections). A node
    # survives if it has content, children, or a mark — a bare label alone does
    # not keep an otherwise-empty duplicate alive.
    def prune(node: QuestionNode) -> bool:
        node.children = [c for c in node.children if prune(c)]
        has_marks = node.own_marks is not None or bool(node.declared_marks)
        return bool(node.content) or bool(node.children) or has_marks

    for section in sections:
        section.questions = [q for q in section.questions if prune(q)]
    sections = [s for s in sections if s.questions or s.title is not None]

    return ExamDocument(sections=sections, assets=assets)
