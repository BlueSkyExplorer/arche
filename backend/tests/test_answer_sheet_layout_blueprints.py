"""High-fidelity OOXML blueprint regression tests.

These pure tests deliberately use a source document with styles/layout different
from defaults.  They prove that renderer output inherits source layout primitives
rather than reconstructing arbitrary generic python-docx defaults.
"""
# ruff: noqa: E501
from __future__ import annotations

from copy import deepcopy
from io import BytesIO

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.shared import Mm, Pt

from app.services.template_import import import_template_docx


def _source_docx() -> bytes:
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = Mm(12)
    sec.bottom_margin = Mm(13)
    doc.add_paragraph("SCHOOL {{school_name}}")
    heading = doc.add_paragraph("甲部 多項選擇題 (30分)")
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    heading.paragraph_format.space_before = Pt(2)
    heading.paragraph_format.space_after = Pt(1)
    heading.runs[0].bold = True

    mcq = doc.add_table(rows=2, cols=4)
    for index, value in enumerate(["題號", "答案", "題號", "答案"]):
        mcq.cell(0, index).text = value
        mcq.cell(0, index).paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    for col in mcq.columns:
        col.width = Mm(31)
    mcq.cell(1, 0).text, mcq.cell(1, 1).text = "1", "C"

    root = doc.add_paragraph("Q1")
    root.paragraph_format.left_indent = Mm(4)
    root.paragraph_format.space_before = Pt(0)
    root.paragraph_format.space_after = Pt(0)
    root.paragraph_format.tab_stops.add_tab_stop(Mm(160), WD_TAB_ALIGNMENT.RIGHT)
    root.add_run("\t")
    root.add_run("(2分)")
    sub = doc.add_paragraph("(a)")
    sub.paragraph_format.left_indent = Mm(8)
    sub.paragraph_format.space_before = Pt(0)
    sub.paragraph_format.space_after = Pt(0)
    sub.paragraph_format.tab_stops.add_tab_stop(Mm(160), WD_TAB_ALIGNMENT.RIGHT)
    sub.add_run("\t")
    sub.add_run("(2分)")
    # A same-line chain line: sub label + subsub label + answer + marks, all on
    # one logical line separated by tabs (Sample (C) hierarchy chaining).
    chain = doc.add_paragraph("(b)\t(i)\t組織液源頭\t(1分)")
    chain.paragraph_format.left_indent = Mm(10)
    chain.paragraph_format.tab_stops.add_tab_stop(Mm(160), WD_TAB_ALIGNMENT.RIGHT)
    answer = doc.add_paragraph("source answer ignored")
    answer.paragraph_format.left_indent = Mm(12)
    answer.paragraph_format.space_after = Pt(0)

    answer_table = doc.add_table(rows=2, cols=3)
    for col in answer_table.columns:
        col.width = Mm(28)
    answer_table.cell(0, 0).text = "構造"
    answer_table.cell(0, 1).text = "風媒花"
    answer_table.cell(0, 2).text = "蟲媒花"
    footer = sec.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.add_run("Page ")

    raw = BytesIO()
    doc.save(raw)
    return raw.getvalue()


def test_import_captures_content_free_ooxml_blueprints() -> None:
    source = _source_docx()
    draft = import_template_docx(source)

    assert draft.source_docx_sha256
    assert draft.layout_blueprint["schema_version"] == 1
    roles = draft.layout_blueprint["paragraph_roles"]
    assert set(("metadata", "section_heading", "root_question", "sub_question", "answer_paragraph", "marks", "footer")) <= set(roles)
    # Blueprint serializes formatting primitives, not teacher answer content.
    assert "source answer ignored" not in str(draft.layout_blueprint)
    assert "tabs" in roles["root_question"]["pPr"]
    assert "w:ind" in roles["sub_question"]["pPr"]
    assert roles["root_question"]["marks_same_line"] is True
    assert draft.layout_blueprint["parent_totals_by_depth"]["0"] is True
    assert draft.layout_blueprint["tables"]["mcq"]["tblGrid"]
    assert draft.layout_blueprint["tables"]["answer_table"]["tblGrid"]
    # Same-line label chain evidence: sub(+subsub)+answer+marks on one line.
    chains = draft.layout_blueprint["label_chains"]
    assert any(entry["depth"] == 2 for entry in chains)  # sub + subsub chained
    assert any(entry["sub"] == "(b)" and entry["subsub"] == "(i)" for entry in chains)
    # Chain blueprints are content-free: no source answer text retained.
    assert "組織液源頭" not in str(draft.layout_blueprint)


def test_blueprint_is_deeply_immutable_from_later_document_mutation() -> None:
    source = _source_docx()
    first = import_template_docx(source).layout_blueprint
    changed = Document(BytesIO(source))
    changed.paragraphs[2].paragraph_format.left_indent = Mm(99)
    raw = BytesIO()
    changed.save(raw)

    assert first != import_template_docx(raw.getvalue()).layout_blueprint
    assert first == deepcopy(first)
