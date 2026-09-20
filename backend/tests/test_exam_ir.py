"""Exam IR schema tests: arbitrary depth, leaf-only marks, block invariants."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.exam.ir import (
    AssetReference,
    BBox,
    ContentBlock,
    DeclaredMarkEvidence,
    ExamDocument,
    LayoutReference,
    QuestionNode,
    SourceEvidence,
)


def _para(text: str) -> ContentBlock:
    return ContentBlock(kind="paragraph", text=text, source=SourceEvidence(source_text=text))


def test_question_node_arbitrary_depth() -> None:
    # 3 -> b -> ii -> … has no fixed depth limit.
    node = QuestionNode(
        label="3",
        children=[
            QuestionNode(
                label="(b)",
                children=[
                    QuestionNode(label="(ii)", own_marks=Decimal("2"), content=[_para("answer")]),
                ],
            ),
        ],
    )
    assert node.children[0].children[0].own_marks == Decimal("2")
    # two more levels deep is also valid
    deep = QuestionNode(
        label="1",
        children=[
            QuestionNode(
                label="(a)",
                children=[
                    QuestionNode(
                        label="(i)",
                        children=[QuestionNode(label="(1)", own_marks=Decimal("1"))],
                    )
                ],
            )
        ],
    )
    assert deep.children[0].children[0].children[0].own_marks == Decimal("1")


def test_non_leaf_with_own_marks_rejected() -> None:
    with pytest.raises(ValidationError):
        QuestionNode(
            label="3",
            own_marks=Decimal("5"),
            children=[QuestionNode(label="(b)", own_marks=Decimal("2"))],
        )


def test_image_block_requires_asset() -> None:
    with pytest.raises(ValidationError):
        ContentBlock(kind="image")


def test_table_block_requires_rows() -> None:
    with pytest.raises(ValidationError):
        ContentBlock(kind="table")


def test_non_image_block_rejects_asset() -> None:
    with pytest.raises(ValidationError):
        ContentBlock(kind="paragraph", text="x", asset=AssetReference(local_id="a"))


def test_bbox_ordered() -> None:
    with pytest.raises(ValidationError):
        BBox(x0=0.8, y0=0.0, x1=0.2, y1=1.0)
    assert BBox(x0=0.0, y0=0.0, x1=1.0, y1=1.0).x1 == 1.0


def test_semantic_and_layout_are_separate() -> None:
    block = ContentBlock(
        kind="paragraph",
        text="2 + 2 = ?",
        source=SourceEvidence(page=3, block_id="b12", source_text="2 + 2 = ?"),
        layout=LayoutReference(font="Times New Roman", bold=True),
    )
    assert block.text == "2 + 2 = ?"  # semantic
    assert block.layout.font == "Times New Roman"  # formatting, kept separately
    assert block.source.page == 3


def test_declared_marks_are_evidence_not_truth() -> None:
    node = QuestionNode(
        label="1",
        declared_marks=[DeclaredMarkEvidence(value=Decimal("4"), raw_text="(4 marks)")],
        children=[
            QuestionNode(label="(a)", own_marks=Decimal("2")),
            QuestionNode(label="(b)", own_marks=Decimal("2")),
        ],
    )
    assert node.declared_marks[0].value == Decimal("4")
    assert node.own_marks is None  # parent has no own mark


def test_exam_document_holds_assets_and_meta() -> None:
    doc = ExamDocument(
        school_name="Test School",
        assets=[AssetReference(local_id="img1", mime_type="image/png")],
        meta={"provider": "rule-based"},
    )
    assert doc.school_name == "Test School"
    assert doc.assets[0].local_id == "img1"
    assert doc.meta["provider"] == "rule-based"
