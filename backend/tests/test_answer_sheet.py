"""Deterministic answer-sheet extractor unit tests (no LLM, no real files)."""

from decimal import Decimal

from app.exam.extraction.answer_sheet import (
    AnswerImage,
    AnswerParagraph,
    AnswerTable,
    _build_tree,
    compute_warnings,
    extract_answer_sheet,
    leading_labels,
    parse_marks,
    parse_mcq,
    parse_question_table,
    sheet_from_dict,
    sheet_to_dict,
    strip_marks,
)
from app.exam.parsing.blocks import BlockKind, DocumentBlock, ParseResult, SourceReference


def _text(text: str, idx: int) -> DocumentBlock:
    return DocumentBlock(
        id=f"b{idx:04d}", kind=BlockKind.TEXT, text=text, order=idx,
        source=SourceReference(file_name="a.doc"),
    )


def _table(rows: list[list[str]], idx: int, meta: dict | None = None) -> DocumentBlock:
    return DocumentBlock(
        id=f"b{idx:04d}", kind=BlockKind.TABLE, order=idx, rows=rows, meta=meta or {}
    )


# --- marks -------------------------------------------------------------------


def test_parse_marks_variants() -> None:
    assert parse_marks("二氧化碳(1分)") == Decimal("1")
    assert parse_marks("(1分)x3") == Decimal("3")
    assert parse_marks("(2分)") == Decimal("2")
    assert parse_marks("(1分)(1分)") == Decimal("2")
    assert parse_marks("柱頭1分") == Decimal("1")
    assert parse_marks("帶氧血(1)") == Decimal("1")
    assert parse_marks("(其中一項，1)") == Decimal("1")
    assert parse_marks("(每項1分) (2分)") == Decimal("2")  # hint ignored


def test_parse_marks_ignores_clock_time() -> None:
    assert parse_marks("下午1時30分") is None
    assert parse_marks("上午5時及下午3時30分 / 下午4時") is None
    assert parse_marks("下午1時30分(1分)") == Decimal("1")


def test_strip_marks_preserves_time() -> None:
    assert "下午1時30分" in strip_marks("(c)(i) 下午1時 / 下午1時30分(1分)")
    assert strip_marks("二氧化碳(1分)") == "二氧化碳"
    assert strip_marks("水作為溶劑。(其中一項，1)") == "水作為溶劑。"


# --- content-level marking points (RED: additive AnswerContent marks) --------


def test_text_two_marking_points_become_two_paragraphs_with_marks() -> None:
    blocks = [
        _text("乙部　　結構題 (50分)", 0),
        _text("Q1. (a) 二氧化碳 (1分)", 1),
        _text("尿素 (1分)", 2),
    ]
    sheet = extract_answer_sheet(ParseResult(blocks=blocks, source_name="a.doc", format="docx"))
    leaf = sheet.sections[0].questions[0].children[0]
    paras = [c for c in leaf.answer_content if isinstance(c, AnswerParagraph)]
    assert [(p.text, p.marks) for p in paras] == [
        ("二氧化碳", Decimal("1")),
        ("尿素", Decimal("1")),
    ]
    assert [(p.text, p.mark_raw) for p in paras] == [
        ("二氧化碳", "(1分)"),
        ("尿素", "(1分)"),
    ]
    # effective leaf total = sum of content-level marks
    assert leaf.effective_marks() == Decimal("2")


def test_text_nested_sub_sub_marking_points_retained() -> None:
    blocks = [
        _text("乙部　　結構題 (50分)", 0),
        _text("Q1. (b) (ii) statement one (1分)", 1),
        _text("statement two (1分)", 2),
    ]
    sheet = extract_answer_sheet(ParseResult(blocks=blocks, source_name="a.doc", format="docx"))
    leaf = sheet.sections[0].questions[0].children[0].children[0]
    paras = [c for c in leaf.answer_content if isinstance(c, AnswerParagraph)]
    assert [(p.text, p.marks) for p in paras] == [
        ("statement one", Decimal("1")),
        ("statement two", Decimal("1")),
    ]


def test_multiply_token_preserves_raw_notation() -> None:
    blocks = [
        _text("乙部　　結構題 (50分)", 0),
        _text("Q1. (a) 構造對比 (1分)x3", 1),
    ]
    sheet = extract_answer_sheet(ParseResult(blocks=blocks, source_name="a.doc", format="docx"))
    leaf = sheet.sections[0].questions[0].children[0]
    paras = [c for c in leaf.answer_content if isinstance(c, AnswerParagraph)]
    assert paras[0].mark_raw == "(1分)x3"
    assert paras[0].marks == Decimal("3")
    assert leaf.effective_marks() == Decimal("3")


def test_table_same_path_rows_do_not_overwrite_marks() -> None:
    rows = [
        ["Q1.", "(a)", "", "睾丸", "(1分)"],
        ["", "", "", "肝", "(1分)"],
    ]
    q_label, leaves = parse_question_table(_table(rows, 0))
    tree = _build_tree(q_label, leaves)
    leaf = tree.children[0]
    # two content rows, each with its own 1 mark -> no silent overwrite
    marked = [c for c in leaf.answer_content if getattr(c, "marks", None) is not None]
    assert len(marked) == 2
    assert all(c.marks == Decimal("1") for c in marked)  # type: ignore[attr-defined]
    assert leaf.effective_marks() == Decimal("2")


# --- labels ------------------------------------------------------------------


def test_leading_labels() -> None:
    assert leading_labels("Q1.") == (["Q1"], "")
    assert leading_labels("Q3a柱頭1分") == (["Q3", "a"], "柱頭1分")
    assert leading_labels("(b)(i)組織液") == (["(b)", "(i)"], "組織液")
    assert leading_labels("b構造X是花粉管") == (["b"], "構造X是花粉管")
    assert leading_labels("Q9 (a) 以下任何兩項") == (["Q9", "(a)"], "以下任何兩項")
    assert leading_labels("尿素(1分)") == ([], "尿素(1分)")  # continuation


# --- MCQ ---------------------------------------------------------------------


def test_parse_mcq() -> None:
    rows = [
        ["題號", "答案", "題號", "答案"],
        ["1", "B", "16", "C"],
        ["2", "C", "17", "C"],
    ]
    assert parse_mcq(_table(rows, 0)) == [("1", "B"), ("16", "C"), ("2", "C"), ("17", "C")]


def test_parse_mcq_non_mcq_returns_none() -> None:
    assert parse_mcq(_table([["Q1.", "(a)", "", "內容", "(1分)"]], 0)) is None


def test_mcq_grid_preserves_exact_order_and_content() -> None:
    # Word UAT flagged possible MCQ reordering: assert the FULL ordered list
    # survives source grid -> extraction (row-major reading order).
    rows = [["題號", "答案", "題號", "答案"]] + [
        [str(n), "ABCD"[n % 4], str(n + 15), "ABCD"[(n + 15) % 4]] for n in range(1, 16)
    ]
    mcq = parse_mcq(_table(rows, 0))
    assert mcq is not None
    assert len(mcq) == 30
    # Reading order interleaves column pairs row by row: (1,16),(2,17)…
    assert mcq[0] == ("1", "B")
    assert mcq[1] == ("16", "A")
    assert mcq[28] == ("15", "D")
    assert mcq[29] == ("30", "C")
    # question numbers strictly 1..30, no duplicates
    numbers = [n for n, _ in mcq]
    assert sorted(numbers, key=int) == [str(i) for i in range(1, 31)]


# --- table format ------------------------------------------------------------


def test_parse_question_table_forward_fill() -> None:
    rows = [
        ["Q1.", "(a)", "", "睾丸", "(1分)"],
        ["", "(b)", "", "X：46條", "(2分)"],
        ["", "(c)", "(i)", "種子散播", "(1分)"],
        ["", "", "(ii)", "避免擠迫", "(1分)"],
    ]
    q_label, leaves = parse_question_table(_table(rows, 0))
    assert q_label == "Q1."
    assert leaves == [
        (
            ["(a)"],
            ["睾丸"],
            [AnswerParagraph("睾丸", Decimal("1"), "(1分)")],
            Decimal("1"),
            False,
        ),
        (
            ["(b)"],
            ["X：46條"],
            [AnswerParagraph("X：46條", Decimal("2"), "(2分)")],
            Decimal("2"),
            False,
        ),
        (
            ["(c)", "(i)"],
            ["種子散播"],
            [AnswerParagraph("種子散播", Decimal("1"), "(1分)")],
            Decimal("1"),
            False,
        ),
        (
            ["(c)", "(ii)"],
            ["避免擠迫"],
            [AnswerParagraph("避免擠迫", Decimal("1"), "(1分)")],
            Decimal("1"),
            False,
        ),
    ]
    tree = _build_tree(q_label, leaves)
    assert tree.label == "Q1."
    assert [c.label for c in tree.children] == ["(a)", "(b)", "(c)"]
    assert tree.children[2].children[0].label == "(i)"
    assert tree.children[2].children[0].marks == Decimal("1")
    assert tree.total() == Decimal("5")


def test_question_table_multiline_cell_preserved() -> None:
    # A cell whose source had multiple paragraphs/lines must stay as separate lines.
    rows = [["Q1.", "(a)", "", "花瓣 細小\n柱頭 呈羽狀\n雄蕊 懸垂", "(1分)x3"]]
    q_label, leaves = parse_question_table(_table(rows, 0))
    assert leaves[0][1] == ["花瓣 細小", "柱頭 呈羽狀", "雄蕊 懸垂"]
    assert leaves[0][2] == [
        AnswerParagraph("花瓣 細小", Decimal("1"), "(1分)x3"),
        AnswerParagraph("柱頭 呈羽狀", Decimal("1"), "(1分)x3"),
        AnswerParagraph("雄蕊 懸垂", Decimal("1"), "(1分)x3"),
    ]
    assert leaves[0][3] == Decimal("3")


def test_question_table_non_text_cell() -> None:
    # A diagram cell -> flagged non-text, no garbled text in the answer.
    rows = [
        ["Q3.", "(c)", "", "", "(1分)"],
    ]
    meta = {"non_text_cells": {"0:3": "drawing"}}
    q_label, leaves = parse_question_table(_table(rows, 0, meta))
    assert leaves[0][0] == ["(c)"]
    assert leaves[0][1] == []
    assert leaves[0][3:] == (Decimal("1"), True)
    tree = _build_tree(q_label, leaves)
    assert tree.children[0].has_non_text_content is True
    assert tree.children[0].answer == []


def test_question_table_preserves_structured_table_and_image_reference() -> None:
    table = _table(
        [["Q1.", "(a)", "", "構造 | 風媒花 | 蟲媒花", "(2分)"]],
        0,
        {
            "non_text_cells": {"0:3": "image"},
            "cell_content": {
                "0:3": [
                    {
                        "kind": "table",
                        "rows": [["構造", "風媒花", "蟲媒花"], ["花瓣", "細小", "鮮艷"]],
                    }
                ]
            },
            "cell_assets": {
                "0:3": [{"local_id": "shape-0", "mime_type": "image/png"}]
            },
        },
    )
    q_label, leaves = parse_question_table(table)
    tree = _build_tree(q_label, leaves)
    content = tree.children[0].answer_content
    assert isinstance(content[0], AnswerTable)
    assert content[0].rows[0] == ["構造", "風媒花", "蟲媒花"]
    assert content[1] == AnswerImage(local_id="shape-0", mime_type="image/png")


# --- declared vs computed total ----------------------------------------------


def test_declared_total_mismatch_kept_and_flagged() -> None:
    blocks = [
        _text("乙部　　結構題 (50分)", 0),
        _table(
            [["Q1.", "(a)", "", "睾丸", "(1分)"], ["", "(b)", "", "肝", "(52分)"]], 1
        ),
    ]
    sheet = extract_answer_sheet(ParseResult(blocks=blocks, source_name="a.doc", format="docx"))
    sec = sheet.sections[0]
    # both values preserved, leaf marks NOT fudged to fit the declared total
    assert sec.declared_total == Decimal("50")
    assert sec.computed_total() == Decimal("53")
    assert [c.marks for c in sec.questions[0].children] == [Decimal("1"), Decimal("52")]
    w = next(w for w in sheet.warnings if w.code == "declared_total_mismatch")
    assert w.declared == Decimal("50")
    assert w.computed == Decimal("53")
    assert w.section == "乙部　　結構題 (50分)"


def test_declared_total_matches_no_warning() -> None:
    blocks = [
        _text("乙部　　結構題 (3分)", 0),
        _table([["Q1.", "(a)", "", "睾丸", "(1分)"], ["", "(b)", "", "肝", "(2分)"]], 1),
    ]
    sheet = extract_answer_sheet(ParseResult(blocks=blocks, source_name="a.doc", format="docx"))
    assert sheet.sections[0].computed_total() == Decimal("3")
    assert not any(w.code == "declared_total_mismatch" for w in sheet.warnings)


def test_non_text_section_flagged() -> None:
    blocks = [
        _text("乙部　　結構題 (1分)", 0),
        _table([["Q1.", "(a)", "", "", "(1分)"]], 1, {"non_text_cells": {"0:3": "drawing"}}),
    ]
    sheet = extract_answer_sheet(ParseResult(blocks=blocks, source_name="a.doc", format="docx"))
    sec = sheet.sections[0]
    assert sec.has_non_text_content is True
    assert any(w.code == "non_text_content" for w in sheet.warnings)


def test_section_non_text_derived_from_deep_descendant() -> None:
    # a deep sub-sub node with non-text -> section flag derived True (never missed)
    blocks = [
        _text("乙部　　結構題 (1分)", 0),
        _table(
            [["Q1.", "(c)", "(i)", "", "(1分)"]], 1, {"non_text_cells": {"0:3": "drawing"}}
        ),
    ]
    sheet = extract_answer_sheet(ParseResult(blocks=blocks, source_name="a.doc", format="docx"))
    sec = sheet.sections[0]
    node = sec.questions[0].children[0].children[0]  # Q1(c)(i)
    assert node.has_non_text_content is True
    assert sec.has_non_text_content is True  # derived from the descendant


def test_section_standalone_non_text() -> None:
    # a detached image block (not in any question) flags the section, not a node
    blocks = [
        _text("乙部　　結構題 (1分)", 0),
        _table([["Q1.", "(a)", "", "睾丸", "(1分)"]], 1),
        DocumentBlock(id="b0002", kind=BlockKind.IMAGE, order=2),
    ]
    sheet = extract_answer_sheet(ParseResult(blocks=blocks, source_name="a.doc", format="docx"))
    sec = sheet.sections[0]
    assert sec.has_non_text_content is True  # standalone image
    assert sec.questions[0].has_non_text_content is False  # the node itself is clean


# --- marks invariant + serialization (RED) ------------------------------------


def test_legacy_json_without_block_marks_uses_node_marks() -> None:
    # legacy persisted sheet: content blocks carry no marks; node.marks=2
    legacy = {
        "title": "t",
        "sections": [
            {
                "title": "乙部",
                "declared_total": "2",
                "questions": [
                    {
                        "label": "Q1",
                        "answer": ["二氧化碳", "尿素"],
                        "answer_content": [
                            {"kind": "paragraph", "text": "二氧化碳"},
                            {"kind": "paragraph", "text": "尿素"},
                        ],
                        "marks": "2",
                        "children": [],
                    }
                ],
            }
        ],
    }
    sheet = sheet_from_dict(legacy)
    leaf = sheet.sections[0].questions[0]
    assert leaf.effective_marks() == Decimal("2")  # fallback to legacy node.marks
    assert leaf.total() == Decimal("2")
    assert compute_warnings(sheet) is None
    assert not any(w.code == "marking_point_total_mismatch" for w in sheet.warnings)


def test_mismatch_between_block_marks_and_node_marks_warns() -> None:
    legacy = {
        "title": "",
        "sections": [
            {
                "title": "乙部",
                "questions": [
                    {
                        "label": "Q1",
                        "answer_content": [
                            {
                                "kind": "paragraph",
                                "text": "二氧化碳",
                                "marks": "1",
                                "mark_raw": "(1分)",
                            },
                            {
                                "kind": "paragraph",
                                "text": "尿素",
                                "marks": "1",
                                "mark_raw": "(1分)",
                            },
                        ],
                        "marks": "3",
                        "children": [],
                    }
                ],
            }
        ],
    }
    sheet = sheet_from_dict(legacy)
    leaf = sheet.sections[0].questions[0]
    assert leaf.effective_marks() == Decimal("2")
    assert leaf.marks == Decimal("3")
    compute_warnings(sheet)
    w = next(w for w in sheet.warnings if w.code == "marking_point_total_mismatch")
    assert w.declared == Decimal("2")  # content-level sum
    assert w.computed == Decimal("3")  # legacy node.marks — never silently corrected


def test_round_trip_preserves_content_marks_and_raw() -> None:
    blocks = [
        _text("乙部　　結構題 (50分)", 0),
        _text("Q1. (a) 二氧化碳 (1分)", 1),
        _text("尿素 (1分)", 2),
        _text("Q2. (a) 構造對比 (1分)x3", 3),
    ]
    sheet = extract_answer_sheet(ParseResult(blocks=blocks, source_name="a.doc", format="docx"))
    restored = sheet_from_dict(sheet_to_dict(sheet))
    original = sheet.sections[0].questions[0].children[0].answer_content
    restored_content = restored.sections[0].questions[0].children[0].answer_content
    assert original == restored_content
    assert isinstance(restored_content[0], AnswerParagraph)
    assert isinstance(restored_content[1], AnswerParagraph)
    assert restored_content[0].mark_raw == "(1分)"
    assert restored_content[1].marks == Decimal("1")
    q2_content = restored.sections[0].questions[1].children[0].answer_content[0]
    assert isinstance(q2_content, AnswerParagraph)
    assert q2_content.mark_raw == "(1分)x3"
    assert q2_content.marks == Decimal("3")


def test_extract_answer_sheet_table_format() -> None:
    blocks = [
        _text("余振強紀念中學", 0),
        _text("中四級 生物科 (參考答案)", 1),
        _text("甲部　　多項選擇題 (30分)", 2),
        _table([["題號", "答案"], ["1", "B"], ["2", "C"]], 3),
        _text("乙部　　結構題 (50分)", 4),
        _table(
            [["Q1.", "(a)", "", "睾丸", "(1分)"], ["", "(b)", "", "肝", "(2分)"]], 5
        ),
    ]
    parsed = ParseResult(blocks=blocks, source_name="a.doc", format="docx")
    sheet = extract_answer_sheet(parsed)
    assert len(sheet.sections) == 2
    assert sheet.sections[0].mcq == [("1", "B"), ("2", "C")]
    q = sheet.sections[1].questions[0]
    assert q.label == "Q1."
    assert [c.label for c in q.children] == ["(a)", "(b)"]
    assert q.total() == Decimal("3")
