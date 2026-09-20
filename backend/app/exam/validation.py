"""Deterministic validation & reconciliation for the Exam IR.

No LLM. Validates tree consistency, marks invariants (ADR-0002 / ADR-0004),
declared-vs-computed reconciliation, numbering presence, page continuity
(cross-page), asset reference integrity, and aggregates extraction confidence
into a single ``needs_review`` decision.

Marks semantics (the invariant this module enforces):

- ``own_marks`` is authoritative and legal on a leaf only.
- ``known_marks_total`` is the sum of *known* leaf marks; unknown leaves add 0.
- ``marks_complete`` is true only when every descendant leaf has a known mark.
- ``computed_marks`` is the leaf sum when complete and ``None`` when any leaf
  mark is unknown — it is never silently the known subtotal, so downstream code
  cannot mistake a partial total for a complete one.
- ``needs_review`` is separate: it also reflects low confidence, numbering
  conflicts, page gaps, and asset issues, so it is never a proxy for
  ``marks_complete``.
"""

from __future__ import annotations

from decimal import Decimal

from app.exam.ir import (
    ExamDocument,
    ExtractionConfidence,
    QuestionNode,
    ValidationIssue,
    ValidationReport,
)

LOW_CONFIDENCE_THRESHOLD = 0.5


def known_marks_total(node: QuestionNode) -> Decimal:
    """Sum of all *known* descendant leaf marks (unknown leaves contribute 0)."""
    if node.children:
        return sum((known_marks_total(child) for child in node.children), Decimal("0"))
    return node.own_marks if node.own_marks is not None else Decimal("0")


def marks_complete(node: QuestionNode) -> bool:
    """True when every descendant leaf carries a known ``own_marks``."""
    if node.children:
        return all(marks_complete(child) for child in node.children)
    return node.own_marks is not None


def computed_marks(node: QuestionNode) -> Decimal | None:
    """The authoritative mark of a subtree, or ``None`` when incomplete."""
    return known_marks_total(node) if marks_complete(node) else None


def document_known_total(doc: ExamDocument) -> Decimal:
    return sum(
        (known_marks_total(q) for section in doc.sections for q in section.questions),
        Decimal("0"),
    )


def document_marks_complete(doc: ExamDocument) -> bool:
    return all(marks_complete(q) for section in doc.sections for q in section.questions)


def computed_total(doc: ExamDocument) -> Decimal | None:
    """The authoritative paper total, or ``None`` when any question is incomplete."""
    total = Decimal("0")
    for section in doc.sections:
        for question in section.questions:
            value = computed_marks(question)
            if value is None:
                return None
            total += value
    return total


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
    if node.own_marks is not None and node.children:
        issues.append(
            ValidationIssue(
                code="non_leaf_with_marks",
                severity="blocking",
                message="a node with children cannot carry an authoritative own_marks",
                location=path,
                source=source,
            )
        )
        flags["needs_review"] = True

    # Unknown marks: a leaf with no detected mark stays None, never 0.
    if not node.children and node.own_marks is None:
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
        empty = not node.content and not node.children and node.own_marks is None
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

    # Declared vs computed: only comparable when the subtree is complete. When
    # marks are incomplete there is no false "mismatch" — the unknown_marks
    # issues already drive review.
    if node.declared_marks:
        declared = sum((m.value for m in node.declared_marks), Decimal("0"))
        computed = computed_marks(node)
        if computed is not None and declared != computed:
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
            values = [computed_marks(q) for q in section.questions]
            if all(value is not None for value in values):
                computed = sum((v for v in values if v is not None), Decimal("0"))
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
    if doc.declared_total is not None and total is not None and doc.declared_total != total:
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
        marks_complete=document_marks_complete(doc),
        known_marks_total=document_known_total(doc),
        computed_total=total,
        confidence=confidence,
    )
