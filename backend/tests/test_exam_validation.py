"""Deterministic validation engine tests over the Exam IR.

Covers: normal documents, nested multipart, cross-page reconciliation, unknown
marks, declared-vs-computed mismatch (total + subtotal), missing numbering,
orphan nodes, image/table/equation blocks, asset reference integrity, and
low-confidence extraction.
"""

from decimal import Decimal

from app.exam.ir import (
    AssetReference,
    ContentBlock,
    ExamDocument,
    QuestionNode,
    Section,
    SourceEvidence,
)
from app.exam.validation import computed_total, validate_exam_document


def _para(text: str, page: int | None = None) -> ContentBlock:
    return ContentBlock(
        kind="paragraph",
        text=text,
        source=SourceEvidence(page=page, source_text=text),
    )


def _q(
    label: str | None = None,
    marks: Decimal | None = None,
    content=(),
    children=(),
    confidence: float = 1.0,
    declared_marks=(),
) -> QuestionNode:
    return QuestionNode(
        label=label,
        marks=marks,
        content=list(content),
        children=list(children),
        confidence=confidence,
        declared_marks=list(declared_marks),
    )


def _sec(title: str | None = None, questions=(), declared_subtotal=None) -> Section:
    return Section(title=title, questions=list(questions), declared_subtotal=declared_subtotal)


def _codes(report) -> list[str]:
    return [issue.code for issue in report.issues]


def test_normal_document_no_issues() -> None:
    doc = ExamDocument(
        declared_total=Decimal("5"),
        sections=[
            _sec(
                "A",
                [
                    _q(
                        "1",
                        content=[_para("2+2?")],
                        children=[
                            _q("(a)", marks=Decimal("2"), content=[_para("a")]),
                            _q("(b)", marks=Decimal("3"), content=[_para("b")]),
                        ],
                    )
                ],
            )
        ],
    )
    report = validate_exam_document(doc)
    assert report.issues == []
    assert report.needs_review is False
    assert report.computed_total == Decimal("5")


def test_nested_multipart_3_b_ii() -> None:
    doc = ExamDocument(
        sections=[
            _sec(
                "A",
                [
                    _q(
                        "3",
                        children=[
                            _q(
                                "(b)",
                                children=[
                                    _q("(i)", marks=Decimal("1"), content=[_para("i")]),
                                    _q("(ii)", marks=Decimal("2"), content=[_para("ii")]),
                                ],
                            )
                        ],
                    )
                ],
            )
        ],
    )
    report = validate_exam_document(doc)
    assert report.computed_total == Decimal("3")
    assert "non_leaf_with_marks" not in _codes(report)
    assert "declared_computed_mismatch" not in _codes(report)


def test_cross_page_contiguous_is_not_flagged() -> None:
    doc = ExamDocument(
        sections=[
            _sec(
                "A",
                [
                    _q(
                        "1",
                        content=[_para("stem", page=1)],
                        children=[_q("(b)", marks=Decimal("2"), content=[_para("b", page=2)])],
                    )
                ],
            )
        ],
    )
    report = validate_exam_document(doc)
    assert "page_gap" not in _codes(report)
    assert "page_order" not in _codes(report)


def test_page_gap_flagged() -> None:
    doc = ExamDocument(
        sections=[
            _sec(
                "A",
                [_q("1", content=[_para("stem", page=1), _para("more", page=3)])],
            )
        ],
    )
    report = validate_exam_document(doc)
    assert "page_gap" in _codes(report)
    assert report.needs_review is True


def test_page_out_of_order_flagged() -> None:
    doc = ExamDocument(
        sections=[
            _sec(
                "A",
                [_q("1", content=[_para("a", page=2), _para("b", page=1)])],
            )
        ],
    )
    report = validate_exam_document(doc)
    assert "page_order" in _codes(report)


def test_unknown_marks_not_coerced_to_zero() -> None:
    doc = ExamDocument(
        sections=[_sec("A", [_q("1", marks=None, content=[_para("no marks")])])],
    )
    report = validate_exam_document(doc)
    assert "unknown_marks" in _codes(report)
    assert report.needs_review is True
    assert report.computed_total == Decimal("0")


def test_declared_total_mismatch() -> None:
    doc = ExamDocument(
        declared_total=Decimal("100"),
        sections=[_sec("A", [_q("1", marks=Decimal("2"), content=[_para("x")])])],
    )
    report = validate_exam_document(doc)
    assert "declared_computed_mismatch" in _codes(report)
    assert report.needs_review is True
    assert report.computed_total == Decimal("2")


def test_section_subtotal_mismatch() -> None:
    doc = ExamDocument(
        sections=[
            _sec(
                "A",
                declared_subtotal=Decimal("9"),
                questions=[_q("1", marks=Decimal("2"), content=[_para("x")])],
            )
        ],
    )
    report = validate_exam_document(doc)
    assert "declared_computed_mismatch" in _codes(report)


def test_missing_numbering() -> None:
    doc = ExamDocument(
        sections=[_sec("A", [_q(None, marks=Decimal("2"), content=[_para("x")])])],
    )
    report = validate_exam_document(doc)
    assert "missing_numbering" in _codes(report)
    assert report.needs_review is True


def test_orphan_node() -> None:
    doc = ExamDocument(sections=[_sec("A", [_q(None)])])
    report = validate_exam_document(doc)
    assert "orphan_node" in _codes(report)
    assert report.needs_review is True


def test_image_table_equation_blocks_reconcile() -> None:
    asset = AssetReference(local_id="img1", mime_type="image/png")
    doc = ExamDocument(
        sections=[
            _sec(
                "A",
                [
                    _q(
                        "1",
                        marks=Decimal("3"),
                        content=[
                            ContentBlock(kind="image", asset=asset, source=SourceEvidence(page=1)),
                            ContentBlock(
                                kind="table",
                                rows=[["a", "b"], ["c", "d"]],
                                source=SourceEvidence(page=1),
                            ),
                            ContentBlock(
                                kind="equation",
                                text="x = 2",
                                source=SourceEvidence(page=1),
                            ),
                        ],
                    )
                ],
            )
        ],
        assets=[asset],
    )
    report = validate_exam_document(doc)
    assert "dangling_asset_reference" not in _codes(report)
    assert "unreferenced_asset" not in _codes(report)


def test_dangling_asset_reference() -> None:
    doc = ExamDocument(
        sections=[
            _sec(
                "A",
                [
                    _q(
                        "1",
                        content=[
                            ContentBlock(
                                kind="image",
                                asset=AssetReference(local_id="missing"),
                            )
                        ],
                    )
                ],
            )
        ],
    )
    report = validate_exam_document(doc)
    assert "dangling_asset_reference" in _codes(report)
    assert report.needs_review is True


def test_unreferenced_asset_is_info() -> None:
    doc = ExamDocument(
        sections=[_sec("A", [_q("1", marks=Decimal("1"))])],
        assets=[AssetReference(local_id="unused")],
    )
    report = validate_exam_document(doc)
    assert "unreferenced_asset" in _codes(report)
    assert report.needs_review is False  # info only


def test_low_confidence_extraction() -> None:
    doc = ExamDocument(
        sections=[_sec("A", [_q("1", marks=Decimal("2"), content=[_para("x")], confidence=0.3)])],
    )
    report = validate_exam_document(doc)
    assert report.needs_review is True
    assert report.confidence.min_node == 0.3
    assert any("1" in node for node in report.confidence.low_confidence_nodes)


def test_computed_total_function() -> None:
    doc = ExamDocument(
        sections=[
            _sec(
                "A",
                [
                    _q("1", marks=Decimal("2")),
                    _q(
                        "2",
                        children=[
                            _q("(a)", marks=Decimal("1")),
                            _q("(b)", marks=Decimal("1")),
                        ],
                    ),
                ],
            ),
            _sec("B", [_q("3", marks=Decimal("4"))]),
        ],
    )
    assert computed_total(doc) == Decimal("8")
