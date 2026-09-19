"""Question-ingest service tests (pure functions; no DB required)."""
from decimal import Decimal

import pytest

from app.services.question_ingest import _extract_marks, ingest_question_text

MIXED = """1. Solve 2 + 2. (2 marks)

a) 2

b) 4

2. 計算 12 × 4。 （2分）
"""

NESTED = """Q1. 風媒花與蟲媒花的差異。 （2分）

(a) 花瓣：風媒花細小。 （1分）
(b) 柱頭：
(i) 呈羽狀。
(ii) 帶黏性。 （2分）
"""


def test_splits_numbered_questions() -> None:
    drafts = ingest_question_text(MIXED)
    assert len(drafts) == 2
    q1, q2 = drafts
    assert q1.marks == Decimal("2")
    types = [node.type for node in q1.content_json.content]
    assert "subQuestion" in types
    sub = next(n for n in q1.content_json.content if n.type == "subQuestion")
    assert sub.attrs.label == "(a)"
    assert q2.marks == Decimal("2")
    assert any("計算" in s for s in _texts(q2.content_json))


def _texts(node) -> list[str]:
    out: list[str] = []
    for block in node.content:
        if block.type == "paragraph":
            out.extend(getattr(t, "text", "") for t in block.content)
        elif block.type == "subQuestion":
            for sub in block.content:
                if sub.type == "paragraph":
                    out.extend(getattr(t, "text", "") for t in sub.content)
    return out


def test_marks_absent_when_undetected() -> None:
    drafts = ingest_question_text("1. Write an essay.\n\n2. Draw a graph.\n")
    assert all(d.marks is None for d in drafts)
    assert all(d.needs_review for d in drafts)


def test_detected_marks_are_recorded_as_declared_evidence() -> None:
    drafts = ingest_question_text("1. Solve 2 + 2. (2 marks)\n")
    q = drafts[0]
    assert q.marks == Decimal("2")
    assert not q.needs_review
    assert len(q.declared_marks) == 1
    assert q.declared_marks[0].value == Decimal("2")
    assert "(2 marks)" in q.declared_marks[0].raw_text


def test_internal_title_derived_from_first_line() -> None:
    drafts = ingest_question_text("1. Solve 2 + 2. (2 marks)\n")
    assert drafts[0].internal_title  # non-empty


def test_empty_and_garbage_input_yield_no_drafts() -> None:
    assert ingest_question_text("") == []
    assert ingest_question_text("no numbers here\njust words") == []


def test_answer_lines_preserved_in_body() -> None:
    drafts = ingest_question_text("1. Show your working.\nAns: ______\n")
    assert len(drafts) == 1
    text = "\n".join(_texts(drafts[0].content_json))
    assert "______" in text


def test_docx_ingest_parses_paragraphs() -> None:
    from io import BytesIO

    from docx import Document

    doc = Document()
    for line in MIXED.splitlines():
        if line.strip():
            doc.add_paragraph(line)
    buf = BytesIO()
    doc.save(buf)

    from app.services.question_ingest import ingest_question_docx

    drafts = ingest_question_docx(buf.getvalue())
    assert len(drafts) == 2
    assert drafts[0].marks == Decimal("2")


def test_bad_docx_raises() -> None:
    from app.services.question_ingest import ingest_question_docx

    with pytest.raises(ValueError):
        ingest_question_docx(b"not a zip")


def _docx_bytes(paragraphs: list[str]) -> bytes:
    from io import BytesIO

    from docx import Document

    doc = Document()
    for line in paragraphs:
        doc.add_paragraph(line)
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.mark.db
def test_ingest_endpoint_text(api_client) -> None:
    response = api_client.post(
        "/api/v1/questions/ingest", data={"text": MIXED}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 2
    assert body[0]["marks"] == "2"
    assert body[0]["content_json"]["content"][1]["type"] == "subQuestion"
    assert body[0]["status"] == "draft"


@pytest.mark.db
def test_ingest_endpoint_docx_file(api_client) -> None:
    payload = _docx_bytes([p for p in MIXED.splitlines() if p.strip()])
    response = api_client.post(
        "/api/v1/questions/ingest",
        files={
            "file": (
                "set.docx",
                payload,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 200, response.text
    assert len(response.json()) == 2


@pytest.mark.db
def test_ingest_endpoint_requires_auth(api_client) -> None:
    app = api_client.app
    from app.core.deps import get_current_user

    def deny() -> object:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Authentication required")

    app.dependency_overrides[get_current_user] = deny
    try:
        response = api_client.post(
            "/api/v1/questions/ingest", data={"text": MIXED}
        )
        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.db
def test_ingest_endpoint_rejects_docm_and_garbage(api_client) -> None:
    assert (
        api_client.post(
            "/api/v1/questions/ingest",
            files={"file": ("set.docm", b"PK\x03\x04fake", "application/octet-stream")},
        ).status_code
        == 415
    )
    assert (
        api_client.post("/api/v1/questions/ingest", data={"text": "   "}).status_code == 422
    )
    assert (
        api_client.post("/api/v1/questions/ingest").status_code == 422
    )


@pytest.mark.db
def test_ingest_endpoint_accepts_doc(api_client) -> None:
    from pathlib import Path

    doc_path = Path(__file__).parent / "fixtures" / "school_format.doc"
    if not doc_path.exists():
        pytest.skip("school_format.doc fixture not available")
    doc_bytes = doc_path.read_bytes()
    response = api_client.post(
        "/api/v1/questions/ingest",
        files={"file": ("questions.doc", doc_bytes, "application/msword")},
    )
    assert response.status_code == 200, response.text


def test_splits_q_prefixed_and_nested_subparts() -> None:
    drafts = ingest_question_text(NESTED)
    assert len(drafts) == 1
    q = drafts[0]
    types = [n.type for n in q.content_json.content]
    assert "subQuestion" in types
    # Find sub-question (b) which should contain nested sub-questions
    subs = [n for n in q.content_json.content if n.type == "subQuestion"]
    # (a) and (b)
    assert len(subs) == 2
    b = next(n for n in subs if getattr(n.attrs, "label", "") == "(b)")
    inner = [n for n in b.content if n.type == "subQuestion"]
    assert [getattr(n.attrs, "label", "") for n in inner] == ["(i)", "(ii)"]
    assert q.marks == Decimal("2")


def test_skips_section_headers() -> None:
    text = "甲部　多項選擇題\n\n1. Solve x. (1 mark)\n\n乙部　結構題\n\n2. Draw. (1 mark)\n"
    drafts = ingest_question_text(text)
    assert len(drafts) == 2


def test_ingests_table_row_with_marks_but_empty_answer() -> None:
    from io import BytesIO

    from docx import Document as DocxDocument

    from app.services.question_ingest import ingest_question_docx

    doc = DocxDocument()
    t = doc.add_table(rows=1, cols=5)
    t.cell(0, 0).text = "Q1."
    t.cell(0, 1).text = "(a)"
    t.cell(0, 3).text = ""  # empty answer text
    t.cell(0, 4).text = "(1分) x3"  # marks only
    buf = BytesIO()
    doc.save(buf)

    drafts = ingest_question_docx(buf.getvalue())
    assert len(drafts) == 1
    assert drafts[0].marks == Decimal("3")  # (1分) x3 → 1×3 = 3
    sub = drafts[0].content_json.content[0]
    assert sub.type == "subQuestion"
    assert len(sub.content) >= 1  # placeholder added; no empty-content crash


def test_ingests_subsub_continuation_row() -> None:
    from io import BytesIO

    from docx import Document as DocxDocument

    from app.services.question_ingest import ingest_question_docx

    doc = DocxDocument()
    t = doc.add_table(rows=2, cols=5)
    # row 0: Q1 (c) (i)
    t.cell(0, 0).text = "Q1."
    t.cell(0, 1).text = "(c)"
    t.cell(0, 2).text = "(i)"
    t.cell(0, 3).text = "種子透過動物散播"
    t.cell(0, 4).text = "(1分)"
    # row 1: continuation — sub-part cell empty, only (ii)
    t.cell(1, 2).text = "(ii)"
    t.cell(1, 3).text = "避免擠迫的生長環境"
    t.cell(1, 4).text = "(1分)"
    buf = BytesIO()
    doc.save(buf)

    drafts = ingest_question_docx(buf.getvalue())
    assert len(drafts) == 1
    q = drafts[0]
    assert q.marks == Decimal("2")
    c = q.content_json.content[0]
    assert c.type == "subQuestion" and c.attrs.label == "(c)"
    inner = [n.attrs.label for n in c.content if n.type == "subQuestion"]
    assert inner == ["(i)", "(ii)"]


def test_ingests_table_answers_with_nested_subparts() -> None:
    from io import BytesIO

    from docx import Document as DocxDocument

    from app.services.question_ingest import ingest_question_docx

    doc = DocxDocument()
    t = doc.add_table(rows=3, cols=5)
    # row 0: Q1 (a)
    t.cell(0, 0).text = "Q1."
    t.cell(0, 1).text = "(a)"
    t.cell(0, 3).text = "風媒花花瓣細小"
    t.cell(0, 4).text = "(1分)"
    # row 1: Q1 (b)
    t.cell(1, 1).text = "(b)"
    t.cell(1, 3).text = "後代存有較多遺傳變異"
    t.cell(1, 4).text = "(1分)"
    # row 2: Q2 (a) (i)
    t.cell(2, 0).text = "Q2."
    t.cell(2, 1).text = "(a)"
    t.cell(2, 2).text = "(i)"
    t.cell(2, 3).text = "種子透過動物散播"
    t.cell(2, 4).text = "(1分)"
    buf = BytesIO()
    doc.save(buf)

    drafts = ingest_question_docx(buf.getvalue())
    assert len(drafts) == 2
    q1, q2 = drafts
    assert q1.marks == Decimal("2")  # sum of sub-part marks
    assert q2.marks == Decimal("1")
    top_types = [n.type for n in q1.content_json.content]
    assert top_types == ["subQuestion", "subQuestion"]
    labels = [n.attrs.label for n in q1.content_json.content]
    assert labels == ["(a)", "(b)"]
    q2_sub = q2.content_json.content[0]
    inner = [n.attrs.label for n in q2_sub.content if n.type == "subQuestion"]
    assert inner == ["(i)"]


# --- Marks multiplier tests (TDD: RED first) ---


class TestExtractMarksMultiplier:
    """_extract_marks should multiply when xN/×N follows the mark token."""

    def test_zh_fullwidth_with_x(self) -> None:
        """（1分）x3 → 3"""
        assert _extract_marks("（1分）x3") == Decimal("3")

    def test_zh_fullwidth_with_times(self) -> None:
        """（1分）×3 → 3"""
        assert _extract_marks("（1分）×3") == Decimal("3")

    def test_zh_halfwidth_with_x(self) -> None:
        """(1分)\nx3 → 3"""
        assert _extract_marks("(1分)\nx3") == Decimal("3")

    def test_zh_halfwidth_with_times(self) -> None:
        """(1分)×3 → 3"""
        assert _extract_marks("(1分)×3") == Decimal("3")

    def test_zh_multiplier_2(self) -> None:
        """（2分）x2 → 4"""
        assert _extract_marks("（2分）x2") == Decimal("4")

    def test_zh_multiplier_times_5(self) -> None:
        """（3分）×5 → 15"""
        assert _extract_marks("（3分）×5") == Decimal("15")

    def test_en_with_x(self) -> None:
        """(1 mark)x3 → 3"""
        assert _extract_marks("(1 mark)x3") == Decimal("3")

    def test_en_with_times(self) -> None:
        """(2 marks)×4 → 8"""
        assert _extract_marks("(2 marks)×4") == Decimal("8")

    def test_no_multiplier_still_works(self) -> None:
        """（1分）without multiplier → 1"""
        assert _extract_marks("（1分）") == Decimal("1")

    def test_en_no_multiplier(self) -> None:
        """(3 marks) without multiplier → 3"""
        assert _extract_marks("(3 marks)") == Decimal("3")

    def test_multiple_mark_tokens_with_multipliers(self) -> None:
        """Two mark tokens with multipliers in one cell: (1分)x3 （2分）x2 → 3+4=7"""
        assert _extract_marks("(1分)x3 （2分）x2") == Decimal("7")

    def test_mixed_multiplier_and_plain(self) -> None:
        """(1分)x3 （2分） → 3+2=5"""
        assert _extract_marks("(1分)x3 （2分）") == Decimal("5")

    def test_no_marks_at_all(self) -> None:
        assert _extract_marks("no marks here") == Decimal("0")


def test_ingest_docx_falls_back_to_ai_when_no_rule_drafts(monkeypatch) -> None:
    from decimal import Decimal
    from io import BytesIO

    from docx import Document as DocxDocument

    from app.services import question_ingest
    from app.services.ai_schema import AIQuestion, AISubPart

    doc = DocxDocument()
    t = doc.add_table(rows=1, cols=2)  # rule parser won't recognize this layout
    t.cell(0, 0).text = "第一題"
    t.cell(0, 1).text = "答案是這樣 (2分)"
    buf = BytesIO()
    doc.save(buf)

    fake = [
        AIQuestion(
            label="Q1.",
            marks=Decimal("2"),
            subparts=[AISubPart(label="(a)", text="答案是這樣", marks=Decimal("2"))],
        )
    ]

    class FakeClient:
        enabled = True

    monkeypatch.setattr(question_ingest, "_suggest_questions_ai", lambda s, c: fake)
    monkeypatch.setattr(question_ingest, "AIClient", lambda settings: FakeClient())

    drafts = question_ingest.ingest_question_docx(buf.getvalue())
    assert len(drafts) == 1
    assert drafts[0].marks == Decimal("2")
    assert drafts[0].internal_title == "Q1."


def test_attach_image_assets_places_node_in_subpart() -> None:
    from uuid import uuid4

    from app.services.question_ingest import attach_image_assets, ingest_question_text

    drafts = ingest_question_text("Q1. 題。 （2分）\n\n(a) 花瓣細小 （1分）\n(b) 柱頭 （1分）")
    aid = uuid4()
    attachments = [{"draft_index": 0, "label": "(b)", "image": b"x"}]
    attach_image_assets(drafts, attachments, [aid])
    b = next(
        n
        for n in drafts[0].content_json.content
        if n.type == "subQuestion" and n.attrs.label == "(b)"
    )
    assert any(n.type == "image" and n.attrs.asset_id == aid for n in b.content)


@pytest.mark.db
def test_ingest_endpoint_embeds_cell_image(api_client) -> None:
    from io import BytesIO
    from pathlib import Path

    from docx import Document as DocxDocument

    png = (Path(__file__).parent / "fixtures" / "tiny.png").read_bytes()
    doc = DocxDocument()
    t = doc.add_table(rows=2, cols=5)
    t.cell(0, 0).text = "Q1."
    t.cell(0, 1).text = "(a)"
    t.cell(0, 3).text = "風媒花花瓣細小"
    t.cell(0, 4).text = "(1分)"
    t.cell(1, 1).text = "(b)"
    t.cell(1, 3).add_paragraph().add_run().add_picture(BytesIO(png))
    t.cell(1, 4).text = "(1分)"
    buf = BytesIO()
    doc.save(buf)

    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    resp = api_client.post(
        "/api/v1/questions/ingest", files={"file": ("q.docx", buf.getvalue(), mime)}
    )
    assert resp.status_code == 200, resp.text
    drafts = resp.json()
    assert len(drafts) == 1
    b = next(
        n
        for n in drafts[0]["content_json"]["content"]
        if n["type"] == "subQuestion" and n["attrs"]["label"] == "(b)"
    )
    assert any(n["type"] == "image" for n in b["content"])


def test_table_ingest_recognizes_numeric_and_cjk_question_labels() -> None:
    from io import BytesIO

    from docx import Document as DocxDocument

    from app.services.question_ingest import ingest_question_docx

    doc = DocxDocument()
    t = doc.add_table(rows=2, cols=3)  # [題號, 題目, 分數] layout — NOT [Q, sub, ...]
    t.cell(0, 0).text = "1."
    t.cell(0, 1).text = "風媒花與蟲媒花的差異"
    t.cell(0, 2).text = "(6分)"
    t.cell(1, 0).text = "第2題"
    t.cell(1, 1).text = "計算 12 × 4"
    t.cell(1, 2).text = "（2分）"
    buf = BytesIO()
    doc.save(buf)

    drafts = ingest_question_docx(buf.getvalue())
    assert len(drafts) == 2, drafts
    titles = [d.internal_title for d in drafts]
    assert "1." in titles
    assert "第2題" in titles


def test_mc_answer_grid_with_bare_numbers_still_skipped() -> None:
    from io import BytesIO

    from docx import Document as DocxDocument

    from app.services.question_ingest import ingest_question_docx

    doc = DocxDocument()
    t = doc.add_table(rows=2, cols=4)  # [題號|答案|題號|答案]
    t.cell(0, 0).text = "1"
    t.cell(0, 1).text = "C"
    t.cell(0, 2).text = "16"
    t.cell(0, 3).text = "B"
    t.cell(1, 0).text = "2"
    t.cell(1, 1).text = "D"
    t.cell(1, 2).text = "17"
    t.cell(1, 3).text = "B"
    buf = BytesIO()
    doc.save(buf)

    # bare numbers must not be treated as question numbers
    assert ingest_question_docx(buf.getvalue()) == []