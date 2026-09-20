"""Deterministic validation & reconciliation for the Exam IR.

No LLM. Validates tree consistency, marks invariants (ADR-0002), declared-vs-
computed reconciliation, numbering presence, page continuity (cross-page),
asset reference integrity, and aggregates extraction confidence into a single
``needs_review`` decision.

The AI extracts *semantics*; this module verifies that the result is a
consistent, reviewable structure and derives every computed total from leaf
marks — never from declared values.
"""

from __future__ import annotations

from decimal import Decimal

from app.exam.ir import (
    ExamDocument,
    ExtractionConfidence,
    QuestionNode,
    Section,
    ValidationIssue,
    ValidationReport,
)

LOW_CONFIDENCE_THRESHOLD = 0.5


def _compute_node_marks(node: QuestionNode) -> Decimal:
    if node.children:
        return sum((_compute_node_marks(child) for child in node.children), Decimal("0"))
    return node.marks if node.marks is not None else Decimal("0")


def _computed_section_marks(section: Section) -> Decimal:
    return sum((_compute_node_marks(q) for q in section.questions), Decimal("0"))


def computed_total(doc: ExamDocument) -> Decimal:
    """The authoritative paper total: sum of all leaf marks."""
    return sum((_computed_section_marks(section) for section in doc.sections), Decimal("0"))


def _collect_pages(node: QuestionNode, pages: list[int]) -> None:
    for block in node.content:
        if block.source.page is not None:
            pages.append(block.source.page)
    for child in node.children:
        _collect_pages(child, pages)


def _validate_node(
    node: QuestionNode,
    path: str,
    issues: list[ValidationIssue],
    flags: dict[str, bool],
    referenced_assets: set[str],
    low_confidence_nodes: list[str],
) -> None:
    source = node.source

    if node.confidence < LOW_CONFIDENCE_THRESHOLD:
        low_confidence_nodes.append(path)
        flags["needs_review"] = True

    # Leaf-only marks: the schema already rejects this, but validate defensively.
    if node.marks is not None and node.children:
        issues.append(
            ValidationIssue(
                code="non_leaf_with_marks",
                severity="blocking",
                message="a node with children cannot carry an authoritative mark",
                location=path,
                source=source,
            )
        )
        flags["needs_review"] = True

    # Unknown marks: a leaf with no detected mark stays None, never 0.
    if not node.children and node.marks is None:
        issues.append(
            ValidationIssue(
                code="unknown_marks",
                severity="warning",
                message="leaf has no detected mark (left null, not coerced to 0)",
                location=path,
                source=source,
            )
        )
        flags["needs_review"] = True

    # Numbering presence.
    if node.label is None:
        empty = not node.content and not node.children and node.marks is None
        if empty:
            issues.append(
                ValidationIssue(
                    code="orphan_node",
                    severity="warning",
                    message="node has no label, content, children, or mark",
                    location=path,
                    source=source,
                )
            )
        else:
            issues.append(
                ValidationIssue(
                    code="missing_numbering",
                    severity="warning",
                    message="node has no label and cannot be numbered",
                    location=path,
                    source=source,
                )
            )
        flags["needs_review"] = True

    # Declared vs computed at this node.
    if node.declared_marks:
        declared = sum((m.value for m in node.declared_marks), Decimal("0"))
        computed = _compute_node_marks(node)
        if declared != computed:
            issues.append(
                ValidationIssue(
                    code="declared_computed_mismatch",
                    severity="warning",
                    message=f"declared {declared} != computed {computed}",
                    location=path,
                    source=source,
                )
            )
            flags["needs_review"] = True

    # Asset references in this node's content.
    for block in node.content:
        if block.asset is not None:
            referenced_assets.add(block.asset.local_id)

    # Page continuity: cross-page is fine, but gaps / out-of-order pages warn.
    pages: list[int] = []
    _collect_pages(node, pages)
    previous: int | None = None
    for page in pages:
        if previous is not None:
            if page < previous:
                issues.append(
                    ValidationIssue(
                        code="page_order",
                        severity="warning",
                        message=f"page {page} follows {previous}; possible mis-association",
                        location=path,
                        source=source,
                    )
                )
                flags["needs_review"] = True
            elif page > previous + 1:
                issues.append(
                    ValidationIssue(
                        code="page_gap",
                        severity="warning",
                        message=f"page gap from {previous} to {page}",
                        location=path,
                        source=source,
                    )
                )
                flags["needs_review"] = True
        previous = page

    for index, child in enumerate(node.children):
        child_path = f"{path}/{child.label or f'[{index}]'}"
        _validate_node(
            child, child_path, issues, flags, referenced_assets, low_confidence_nodes
        )


def validate_exam_document(doc: ExamDocument) -> ValidationReport:
    """Run the full deterministic validation pass and return a review report."""
    issues: list[ValidationIssue] = []
    flags: dict[str, bool] = {"needs_review": False}
    referenced_assets: set[str] = set()
    low_confidence_nodes: list[str] = []
    min_confidence = 1.0

    for section_index, section in enumerate(doc.sections):
        section_path = section.title or f"Section {section_index + 1}"
        if section.declared_subtotal is not None:
            computed = _computed_section_marks(section)
            if section.declared_subtotal != computed:
                issues.append(
                    ValidationIssue(
                        code="declared_computed_mismatch",
                        severity="warning",
                        message=f"declared {section.declared_subtotal} != computed {computed}",
                        location=section_path,
                        source=section.source,
                    )
                )
                flags["needs_review"] = True
        for question in section.questions:
            question_path = f"{section_path}/{question.label or '?'}"
            _validate_node(
                question,
                question_path,
                issues,
                flags,
                referenced_assets,
                low_confidence_nodes,
            )
            min_confidence = min(min_confidence, question.confidence)

    total = computed_total(doc)
    if doc.declared_total is not None and doc.declared_total != total:
        issues.append(
            ValidationIssue(
                code="declared_computed_mismatch",
                severity="warning",
                message=f"declared total {doc.declared_total} != computed {total}",
                location="document",
                source=doc.source,
            )
        )
        flags["needs_review"] = True

    # Asset reference integrity.
    declared_asset_ids = {asset.local_id for asset in doc.assets}
    for local_id in sorted(referenced_assets - declared_asset_ids):
        issues.append(
            ValidationIssue(
                code="dangling_asset_reference",
                severity="warning",
                message=f"content references asset {local_id!r} not declared in document assets",
                location="document",
                source=doc.source,
            )
        )
        flags["needs_review"] = True
    for local_id in sorted(declared_asset_ids - referenced_assets):
        issues.append(
            ValidationIssue(
                code="unreferenced_asset",
                severity="info",
                message=f"asset {local_id!r} is not referenced by any content block",
                location="document",
                source=doc.source,
            )
        )

    needs_review = flags["needs_review"] or any(
        issue.severity == "blocking" for issue in issues
    )
    confidence = ExtractionConfidence(
        overall=min_confidence,
        min_node=min_confidence,
        low_confidence_nodes=low_confidence_nodes,
    )
    return ValidationReport(
        issues=issues,
        needs_review=needs_review,
        computed_total=total,
        confidence=confidence,
    )
