"""Rule-based semantic extractor tests.

Covers candidate detection (numbering + marks), hierarchy reconciliation at
arbitrary depth, marks attachment (leaf vs declared subtotal), content
preservation (block identity), source evidence, and safe-failure behaviour.
"""

from decimal import Decimal

from app.exam.extraction import RuleBasedExamExtractor, detect_marks, detect_numbering
from app.exam.ir import AssetReference
from app.exam.parsing.blocks import BlockKind, DocumentBlock, ParseResult, SourceReference
from app.exam.validation import validate_exam_document


def _text(text: str, idx: int, page: int | None = None) -> DocumentBlock:
    return DocumentBlock(
        id=f"b{idx:04d}",
        kind=BlockKind.TEXT,
        text=text,
        order=idx,
        page=page,
        source=SourceReference(file_name="test.docx", page=page),
    )


def _lines(texts: list[str], page: int | None = None) -> list[DocumentBlock]:
    return [_text(t, i, page=page) for i, t in enumerate(texts)]


def _extract(blocks: list[DocumentBlock]):
    parsed = ParseResult(blocks=blocks, source_name="test.docx", format="docx")
    return RuleBasedExamExtractor().extract(parsed)


def _questions(doc):
    return doc.sections[0].questions


# --- candidate detection ---------------------------------------------------


def test_detect_numbering_forms() -> None:
    cases = {
        "1.": ("arabic", 1, "1."),
        "1)": ("arabic", 1, "1)"),
        "1、": ("arabic", 1, "1、"),
        "Q1": ("arabic", 1, "Q1"),
        "Q1.": ("arabic", 1, "Q1."),
        "(a)": ("alpha_lower", 1, "(a)"),
        "a)": ("alpha_lower", 1, "a)"),
        "A.": ("alpha_upper", 1, "A."),
        "(i)": ("roman_lower", 1, "(i)"),
        "(ii)": ("roman_lower", 2, "(ii)"),
        "(1)": ("arabic", 1, "(1)"),
        "3": ("arabic", 3, "3"),
        "3 → (b)": ("arabic", 3, "3"),
    }
    for text, (system, value, token) in cases.items():
        c = detect_numbering(text)
        assert c is not None, text
        assert (c.system, c.value, c.token) == (system, value, token), text


def test_detect_numbering_negative() -> None:
    for text in ("Explain", "(3 marks)", "3 marks", "2024 the year", "Figure 1: a"):
        assert detect_numbering(text) is None, text


def test_detect_marks_forms() -> None:
    assert [c.value for c in detect_marks("Explain (3 marks)")] == [Decimal("3")]
    assert [c.value for c in detect_marks("[3 marks]")] == [Decimal("3")]
    assert [c.value for c in detect_marks("worth 3 marks total")] == [Decimal("3")]
    assert [c.value for c in detect_marks("worth 3 mark")] == [Decimal("3")]
    assert [c.value for c in detect_marks("(3分)")] == [Decimal("3")]
    # no double count of "(3 marks)"
    assert len(detect_marks("(3 marks)")) == 1
    assert detect_marks("no mark here") == []


# --- hierarchy -------------------------------------------------------------


def test_standalone_question() -> None:
    doc = _extract(_lines(["1. Explain the diagram. (2 marks)"]))
    qs = _questions(doc)
    assert len(qs) == 1
    assert qs[0].label == "1."
    assert qs[0].own_marks == Decimal("2")
    assert qs[0].children == []


def test_multipart() -> None:
    doc = _extract(_lines(["1.", "(a) part a", "(b) part b"]))
    q = _questions(doc)[0]
    assert [c.label for c in q.children] == ["(a)", "(b)"]


def test_deep_nested() -> None:
    doc = _extract(_lines(["3.", "(b) level1", "(ii) level2", "(1) level3"]))
    q = _questions(doc)[0]
    assert q.label == "3."
    b = q.children[0]
    assert b.label == "(b)"
    ii = b.children[0]
    assert ii.label == "(ii)"
    one = ii.children[0]
    assert one.label == "(1)"


def test_sibling_transitions() -> None:
    doc = _extract(_lines(["1.", "(i) x", "(ii) y", "(iii) z"]))
    q = _questions(doc)[0]
    assert [c.label for c in q.children] == ["(i)", "(ii)", "(iii)"]


def test_return_to_higher_level() -> None:
    # (i),(ii) are roman; (c) is alpha and must NOT nest under (ii)
    doc = _extract(_lines(["(i) x", "(ii) y", "(c) z"]))
    qs = _questions(doc)
    # all orphaned at root (no parent context), but (c) is a sibling, not a child
    assert [q.label for q in qs] == ["(i)", "(ii)", "(c)"]


def test_question_transition() -> None:
    doc = _extract(_lines(["1. a", "2. b", "3. c"]))
    assert [q.label for q in _questions(doc)] == ["1.", "2.", "3."]


# --- marks -----------------------------------------------------------------


def test_marks_inline() -> None:
    doc = _extract(_lines(["1. Explain (3 marks)"]))
    assert _questions(doc)[0].own_marks == Decimal("3")


def test_marks_separate_block() -> None:
    doc = _extract(_lines(["1. Explain", "(3 marks)"]))
    q = _questions(doc)[0]
    assert q.own_marks == Decimal("3")
    # mark-only block is not accumulated as question content
    assert [c.text for c in q.content] == ["Explain"]


def test_non_leaf_declared_subtotal() -> None:
    doc = _extract(_lines(["1. (5 marks)", "(a) part (2 marks)", "(b) part (3 marks)"]))
    q = _questions(doc)[0]
    assert q.own_marks is None
    assert [m.value for m in q.declared_marks] == [Decimal("5")]
    assert [c.own_marks for c in q.children] == [Decimal("2"), Decimal("3")]


def test_unknown_leaf_marks() -> None:
    doc = _extract(_lines(["1. Explain without marks"]))
    q = _questions(doc)[0]
    assert q.own_marks is None
    report = validate_exam_document(doc)
    assert report.needs_review is True
    assert any(i.code == "unknown_marks" for i in report.issues)


def test_mixed_known_unknown_subtree() -> None:
    doc = _extract(_lines(["1.", "(a) part (2 marks)", "(b) part"]))
    q = _questions(doc)[0]
    assert [c.own_marks for c in q.children] == [Decimal("2"), None]
    report = validate_exam_document(doc)
    assert report.marks_complete is False
    assert report.computed_total is None
    assert report.known_marks_total == Decimal("2")


# --- ambiguity / safe failure ---------------------------------------------


def test_duplicate_numbering_flagged() -> None:
    doc = _extract(_lines(["1.", "(a) x", "(a) y"]))
    q = _questions(doc)[0]
    warnings = doc.meta["extraction_warnings"]
    assert any(w["code"] == "numbering_not_monotonic" for w in warnings)
    assert any(c.confidence < 0.5 for c in q.children)


def test_orphan_numbering_flagged() -> None:
    doc = _extract(_lines(["(ii) orphan"]))
    warnings = doc.meta["extraction_warnings"]
    assert any(w["code"] == "orphan_numbering" for w in warnings)
    report = validate_exam_document(doc)
    assert report.needs_review is True


def test_numbering_level_jump_flagged() -> None:
    doc = _extract(_lines(["1.", "(1) jumped"]))
    warnings = doc.meta["extraction_warnings"]
    assert any(w["code"] == "numbering_level_jump" for w in warnings)


def test_content_before_question_warned() -> None:
    doc = _extract(_lines(["Instructions before questions.", "1. Q"]))
    warnings = doc.meta["extraction_warnings"]
    assert any(w["code"] == "content_before_question" for w in warnings)
    assert len(_questions(doc)) == 1


# --- content preservation --------------------------------------------------


def test_image_table_equation_preserved() -> None:
    img = AssetReference(local_id="img-0", mime_type="image/png")
    blocks = [
        _text("1. See the following:", 0),
        DocumentBlock(id="b0001", kind=BlockKind.IMAGE, order=1, asset=img),
        DocumentBlock(id="b0002", kind=BlockKind.TABLE, order=2, rows=[["a", "b"], ["c", "d"]]),
        DocumentBlock(id="b0003", kind=BlockKind.EQUATION, order=3, text="x = 1"),
    ]
    doc = _extract(blocks)
    node = _questions(doc)[0]
    kinds = [c.kind for c in node.content]
    assert kinds == ["paragraph", "image", "table", "equation"]
    assert node.content[1].asset.local_id == "img-0"
    assert node.content[2].rows == [["a", "b"], ["c", "d"]]
    assert node.content[3].text == "x = 1"
    assert doc.assets == [img]


def test_header_footer_ignored() -> None:
    blocks = [
        DocumentBlock(id="b0000", kind=BlockKind.HEADER, order=0, text="School Name"),
        _text("1. Question", 1),
        DocumentBlock(id="b0002", kind=BlockKind.FOOTER, order=2, text="Page 1"),
    ]
    doc = _extract(blocks)
    assert len(_questions(doc)) == 1
    assert [c.text for c in _questions(doc)[0].content] == ["Question"]


def test_source_evidence_preserved() -> None:
    doc = _extract(_lines(["1. Explain (2 marks)"], page=3))
    q = _questions(doc)[0]
    assert q.source.block_id == "b0000"
    assert q.source.page == 3
    assert q.content[0].source.block_id == "b0000"
    assert q.declared_marks[0].source.source_text == "(2 marks)"


def test_missing_bbox_ok() -> None:
    doc = _extract(_lines(["1. Explain (2 marks)"]))
    q = _questions(doc)[0]
    assert q.source.bbox is None
    assert q.content[0].source.bbox is None


def test_multipage_continuation() -> None:
    blocks = [_text("1. Starts here", 0, page=1), _text("continues here", 1, page=2)]
    doc = _extract(blocks)
    q = _questions(doc)[0]
    assert [c.source.page for c in q.content] == [1, 2]


def test_question_text_across_blocks() -> None:
    doc = _extract(_lines(["1. First sentence.", "Second sentence."]))
    q = _questions(doc)[0]
    assert [c.text for c in q.content] == ["First sentence.", "Second sentence."]


# --- integration -----------------------------------------------------------


def test_integration_q3_nested() -> None:
    blocks = _lines(
        [
            "Q3",
            "(a) part a (2 marks)",
            "(b) part b",
            "(i) part i (1 mark)",
            "(ii) part ii",
        ]
    )
    doc = _extract(blocks)
    report = validate_exam_document(doc)

    q = _questions(doc)[0]
    assert q.label == "Q3"
    a, b = q.children
    assert a.label == "(a)"
    assert b.label == "(b)"
    i, ii = b.children
    assert i.label == "(i)"
    assert ii.label == "(ii)"

    # tree: Q3 -> (a) ; Q3 -> (b) -> (i) ; Q3 -> (b) -> (ii)
    assert a.own_marks == Decimal("2")
    assert i.own_marks == Decimal("1")
    assert ii.own_marks is None  # unknown, never 0

    assert report.known_marks_total == Decimal("3")  # 2 + 1
    assert report.marks_complete is False
    assert report.computed_total is None
    assert report.needs_review is True

    # source evidence still traceable to original blocks
    assert ii.source.block_id == "b0004"
