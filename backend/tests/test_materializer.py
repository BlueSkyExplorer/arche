"""Materializer tests: ExamDocument -> QuestionIngestDraft (deterministic)."""

from decimal import Decimal
from uuid import UUID, uuid4

from app.exam.extraction import RuleBasedExamExtractor
from app.exam.ir import (
    AssetReference,
    ContentBlock,
    DeclaredMarkEvidence,
    ExamDocument,
    QuestionNode,
    Section,
)
from app.exam.materialization import materialize_exam_document
from app.exam.parsing.blocks import BlockKind, DocumentBlock, ParseResult, SourceReference
from app.exam.validation import validate_exam_document
from app.schemas.content import ImageNode, SubQuestionNode, TableNode


def _para(text: str) -> ContentBlock:
    return ContentBlock(kind="paragraph", text=text)


def _q(label=None, own_marks=None, content=(), children=(), declared=(), confidence=1.0):
    return QuestionNode(
        label=label,
        own_marks=own_marks,
        content=list(content),
        children=list(children),
        declared_marks=list(declared),
        confidence=confidence,
    )


def _doc(questions, title=None, subject=None, level=None) -> ExamDocument:
    return ExamDocument(
        title=title, subject=subject, level=level, sections=[Section(questions=questions)]
    )


def _asset_id_for(mapping: dict[str, UUID]):
    def resolver(local_id: str) -> UUID:
        return mapping[local_id]

    return resolver


# --- marks invariant -------------------------------------------------------


def test_leaf_own_marks_carried() -> None:
    doc = _doc([_q("1.", own_marks=Decimal("2"), content=[_para("Explain")])])
    draft = materialize_exam_document(doc)[0]
    assert draft.marks == Decimal("2")
    assert draft.content_json.marks == Decimal("2")


def test_unknown_leaf_marks_stay_none() -> None:
    doc = _doc([_q("1.", own_marks=None, content=[_para("Explain")])])
    draft = materialize_exam_document(doc)[0]
    assert draft.marks is None
    assert draft.content_json.marks is None  # never coerced to 0
    assert draft.needs_review is True


def test_non_leaf_marks_are_none_computed_from_leaves() -> None:
    children = [
        _q("(a)", Decimal("2"), [_para("x")]),
        _q("(b)", Decimal("3"), [_para("y")]),
    ]
    doc = _doc([_q("1.", children=children)])
    draft = materialize_exam_document(doc)[0]
    assert draft.marks is None  # non-leaf: no authoritative mark
    assert draft.content_json.marks is None
    subs = [b for b in draft.content_json.content if isinstance(b, SubQuestionNode)]
    assert [s.attrs.marks for s in subs] == [Decimal("2"), Decimal("3")]


# --- structure -------------------------------------------------------------


def test_arbitrary_depth_preserved() -> None:
    deepest = _q("(1)", Decimal("1"), [_para("x")])
    mid = _q("(ii)", children=[deepest])
    top_child = _q("(b)", children=[mid])
    doc = _doc([_q("3.", children=[top_child])])
    draft = materialize_exam_document(doc)[0]
    (b,) = [x for x in draft.content_json.content if isinstance(x, SubQuestionNode)]
    (ii,) = [x for x in b.content if isinstance(x, SubQuestionNode)]
    (one,) = [x for x in ii.content if isinstance(x, SubQuestionNode)]
    assert b.attrs.label == "(b)"
    assert ii.attrs.label == "(ii)"
    assert one.attrs.label == "(1)"
    assert one.attrs.marks == Decimal("1")


def test_declared_subtotal_preserved_as_evidence() -> None:
    declared = [DeclaredMarkEvidence(value=Decimal("5"), raw_text="(5 marks)")]
    children = [
        _q("(a)", Decimal("2"), [_para("x")]),
        _q("(b)", Decimal("3"), [_para("y")]),
    ]
    doc = _doc([_q("1.", declared=declared, children=children)])
    draft = materialize_exam_document(doc)[0]
    assert [m.value for m in draft.declared_marks] == [Decimal("5")]
    assert draft.marks is None  # subtotal is evidence, not authoritative


# --- content blocks --------------------------------------------------------


def test_image_mapped_with_resolver() -> None:
    asset = AssetReference(local_id="img-0", mime_type="image/png")
    doc = _doc(
        [
            _q(
                "1.",
                own_marks=Decimal("2"),
                content=[_para("See:"), ContentBlock(kind="image", asset=asset)],
            )
        ]
    )
    uid = uuid4()
    draft = materialize_exam_document(doc, asset_id_for=_asset_id_for({"img-0": uid}))[0]
    images = [b for b in draft.content_json.content if isinstance(b, ImageNode)]
    assert len(images) == 1
    assert images[0].attrs.asset_id == uid
    assert draft.needs_review is False


def test_image_without_resolver_flagged_not_silent() -> None:
    asset = AssetReference(local_id="img-0", mime_type="image/png")
    doc = _doc([_q("1.", content=[ContentBlock(kind="image", asset=asset)])])
    draft = materialize_exam_document(doc)[0]
    assert draft.needs_review is True
    assert any("unresolved_image_asset" in i for i in draft.validation_issues)
    assert not any(isinstance(b, ImageNode) for b in draft.content_json.content)


def test_table_mapped() -> None:
    doc = _doc([_q("1.", content=[ContentBlock(kind="table", rows=[["a", "b"], ["c", "d"]])])])
    draft = materialize_exam_document(doc)[0]
    tables = [b for b in draft.content_json.content if isinstance(b, TableNode)]
    assert len(tables) == 1


def test_equation_and_heading_lossy_mapping() -> None:
    doc = _doc(
        [
            _q(
                "1.",
                content=[
                    ContentBlock(kind="equation", text="x = 1"),
                    ContentBlock(kind="heading", text="Sub-head", heading_level=5),
                ],
            )
        ]
    )
    draft = materialize_exam_document(doc)[0]
    kinds = [b.type for b in draft.content_json.content]
    # equation -> paragraph (text preserved); heading -> heading (level clamped to 3)
    assert kinds == ["paragraph", "heading"]
    from app.schemas.content import HeadingNode, ParagraphNode

    para = draft.content_json.content[0]
    assert isinstance(para, ParagraphNode)
    assert para.content[0].text == "x = 1"
    heading = draft.content_json.content[1]
    assert isinstance(heading, HeadingNode)
    assert heading.attrs.level == 3


# --- document metadata -----------------------------------------------------


def test_sections_flattened_with_source_note() -> None:
    doc = ExamDocument(
        subject="Biology",
        level="HKDSE",
        sections=[
            Section(title="Section A", questions=[_q("1.", Decimal("2"), [_para("x")])]),
            Section(title="Section B", questions=[_q("2.", Decimal("3"), [_para("y")])]),
        ],
    )
    drafts = materialize_exam_document(doc)
    assert len(drafts) == 2
    assert [d.subject for d in drafts] == ["Biology", "Biology"]
    assert [d.source_note for d in drafts] == ["Section A", "Section B"]


# --- end-to-end ------------------------------------------------------------


def test_end_to_end_extractor_to_materializer() -> None:
    blocks = [
        DocumentBlock(
            id=f"b{i:04d}", kind=BlockKind.TEXT, text=t, order=i,
            source=SourceReference(file_name="t.docx"),
        )
        for i, t in enumerate(["1. (5 marks)", "(a) part (2 marks)", "(b) part (3 marks)"])
    ]
    parsed = ParseResult(blocks=blocks, source_name="t.docx", format="docx")
    doc = RuleBasedExamExtractor().extract(parsed)
    drafts = materialize_exam_document(doc)
    assert len(drafts) == 1
    draft = drafts[0]
    assert draft.marks is None  # non-leaf
    subs = [b for b in draft.content_json.content if isinstance(b, SubQuestionNode)]
    assert [s.attrs.marks for s in subs] == [Decimal("2"), Decimal("3")]
    # all declared evidence: the stem subtotal plus the leaf marks
    assert [m.value for m in draft.declared_marks] == [Decimal("5"), Decimal("2"), Decimal("3")]


# --- round-trip helper + integration cases A-G -----------------------------


def _node_sig(node: QuestionNode) -> list[tuple]:
    sig = [(node.label, node.own_marks)]
    for child in node.children:
        sig += _node_sig(child)
    return sig


def _sub_sig(sub: SubQuestionNode) -> list[tuple]:
    sig = [(sub.attrs.label, sub.attrs.marks)]
    for block in sub.content:
        if isinstance(block, SubQuestionNode):
            sig += _sub_sig(block)
    return sig


def _doc_sig(doc_node) -> list[tuple]:
    sig: list[tuple] = []
    for block in doc_node.content:
        if isinstance(block, SubQuestionNode):
            sig += _sub_sig(block)
    return sig


def _assert_round_trip(document: ExamDocument, drafts) -> None:
    questions = [q for s in document.sections for q in s.questions]
    assert len(drafts) == len(questions)
    for index, (node, draft) in enumerate(zip(questions, drafts, strict=True), 1):
        assert draft.marks == node.own_marks
        assert draft.content_json.marks == node.own_marks
        # the top-level label lives in internal_title; the subtree is nested
        assert _doc_sig(draft.content_json) == _node_sig(node)[1:]
        assert draft.internal_title == (node.label or f"Question {index}")


def test_case_a_multipart() -> None:
    doc = _doc(
        [
            _q(
                "Q1",
                children=[
                    _q("(a)", Decimal("2"), [_para("x")]),
                    _q("(b)", Decimal("3"), [_para("y")]),
                ],
            )
        ]
    )
    drafts = materialize_exam_document(doc)
    _assert_round_trip(doc, drafts)
    subs = [b for b in drafts[0].content_json.content if isinstance(b, SubQuestionNode)]
    assert [s.attrs.marks for s in subs] == [Decimal("2"), Decimal("3")]


def test_case_b_mixed_known_unknown() -> None:
    doc = _doc(
        [
            _q(
                "Q3",
                children=[
                    _q("(a)", Decimal("2"), [_para("x")]),
                    _q(
                        "(b)",
                        children=[
                            _q("(i)", Decimal("1"), [_para("y")]),
                            _q("(ii)", None, [_para("z")]),
                        ],
                    ),
                ],
            )
        ]
    )
    report = validate_exam_document(doc)
    drafts = materialize_exam_document(doc)
    _assert_round_trip(doc, drafts)

    assert report.known_marks_total == Decimal("3")  # 2 + 1
    assert report.marks_complete is False
    assert report.computed_total is None
    assert report.needs_review is True
    assert drafts[0].needs_review is True
    # ii stays NULL everywhere, never 0
    b = next(
        x
        for x in drafts[0].content_json.content
        if isinstance(x, SubQuestionNode) and x.attrs.label == "(b)"
    )
    ii = next(x for x in b.content if isinstance(x, SubQuestionNode) and x.attrs.label == "(ii)")
    assert ii.attrs.marks is None


def test_case_c_deep_hierarchy_not_flattened() -> None:
    deepest = _q("(1)", Decimal("1"), [_para("x")])
    mid = _q("(ii)", children=[deepest])
    top_child = _q("(b)", children=[mid])
    doc = _doc([_q("3.", children=[top_child])])
    drafts = materialize_exam_document(doc)
    _assert_round_trip(doc, drafts)
    # the fourth level survives as a nested SubQuestionNode, not a flattened string
    (b,) = [x for x in drafts[0].content_json.content if isinstance(x, SubQuestionNode)]
    (ii,) = [x for x in b.content if isinstance(x, SubQuestionNode)]
    (one,) = [x for x in ii.content if isinstance(x, SubQuestionNode)]
    assert one.attrs.label == "(1)"


def test_case_d_rich_content_order_and_asset() -> None:
    asset = AssetReference(local_id="img-0", mime_type="image/png")
    content = [
        ContentBlock(kind="paragraph", text="Intro"),
        ContentBlock(kind="image", asset=asset),
        ContentBlock(kind="caption", text="Figure 1"),
        ContentBlock(kind="table", rows=[["a", "b"]]),
        ContentBlock(kind="equation", text="x = 1"),
        ContentBlock(kind="paragraph", text="End"),
    ]
    doc = _doc([_q("1.", Decimal("2"), content=content)])
    uid = uuid4()
    draft = materialize_exam_document(doc, asset_id_for=_asset_id_for({"img-0": uid}))[0]
    # order preserved: paragraph, image, caption(paragraph), table, equation(paragraph), paragraph
    kinds = [b.type for b in draft.content_json.content]
    assert kinds == ["paragraph", "image", "paragraph", "table", "paragraph", "paragraph"]
    assert isinstance(draft.content_json.content[1], ImageNode)
    assert draft.content_json.content[1].attrs.asset_id == uid
    assert isinstance(draft.content_json.content[3], TableNode)


def test_case_e_declared_subtotal_not_own_marks() -> None:
    declared = [DeclaredMarkEvidence(value=Decimal("5"), raw_text="(5 marks)")]
    doc = _doc(
        [
            _q(
                "1.",
                declared=declared,
                children=[
                    _q("(a)", Decimal("2"), [_para("x")]),
                    _q("(b)", Decimal("3"), [_para("y")]),
                ],
            )
        ]
    )
    draft = materialize_exam_document(doc)[0]
    # children exist + own_marks=None + declared=5 => materialize must NOT set
    # authoritative marks=5; the total is computed from descendants (2+3)
    assert draft.marks is None
    assert draft.content_json.marks is None
    assert [m.value for m in draft.declared_marks] == [Decimal("5")]


def test_case_g_needs_review_preserved() -> None:
    # unknown mark + low confidence -> review state survives materialization
    doc = _doc(
        [
            _q(
                "1.",
                own_marks=None,
                confidence=0.3,
                content=[_para("unclear")],
            )
        ]
    )
    draft = materialize_exam_document(doc)[0]
    assert draft.needs_review is True
    assert draft.marks is None
    # severity is preserved in the validation issue strings
    assert any(i.startswith("warning:") for i in draft.validation_issues)

