"""Renderer-facing high-fidelity layout regression (no LibreOffice needed)."""
# ruff: noqa: E501
from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.shared import Mm

from app.document.renderer import RenderTemplateProfile
from app.document.renderer.answer_sheet import render_answer_sheet
from app.exam.extraction.answer_sheet import sheet_from_dict
from app.schemas.answer_sheet_export import DocumentMetadata
from app.services.template_import import import_template_docx
from tests.test_answer_sheet_exports import _render_config


def _source() -> bytes:
    doc = Document()
    root = doc.add_paragraph("Q1\t(6分)")
    root.paragraph_format.left_indent = Mm(4)
    root.paragraph_format.tab_stops.add_tab_stop(Mm(160), WD_TAB_ALIGNMENT.RIGHT)
    sub = doc.add_paragraph("(a)\tformat answer\t(2分)")
    sub.paragraph_format.left_indent = Mm(8)
    sub.paragraph_format.tab_stops.add_tab_stop(Mm(160), WD_TAB_ALIGNMENT.RIGHT)
    doc.add_paragraph("source answer must not be cloned")
    raw = BytesIO()
    doc.save(raw)
    return raw.getvalue()


def test_renderer_reuses_source_header_metadata_section_footer_and_table_cell_layout() -> None:
    source_document = Document()
    header = source_document.sections[0].header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    header.add_run("format header")
    footer = source_document.sections[0].footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.LEFT
    footer.add_run("format footer")
    metadata = source_document.add_paragraph("source school")
    metadata.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    section = source_document.add_paragraph("乙部 結構題 (50分)")
    section.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    root = source_document.add_paragraph("Q1")
    root.paragraph_format.left_indent = Mm(4)
    leaf = source_document.add_paragraph("(a)\t(2分)")
    leaf.paragraph_format.left_indent = Mm(8)
    leaf.paragraph_format.tab_stops.add_tab_stop(Mm(160), WD_TAB_ALIGNMENT.RIGHT)
    source_document.add_paragraph("source answer")
    table = source_document.add_table(rows=1, cols=2)
    table.cell(0, 0).paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    table.cell(0, 0).text = "source table content"
    table.cell(0, 0).paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    table.cell(0, 1).text = "source table content"
    raw = BytesIO()
    source_document.save(raw)
    source = raw.getvalue()

    draft = import_template_docx(source)
    roles = draft.layout_blueprint["paragraph_roles"]
    assert "header" in roles
    assert "footer" in roles
    assert "metadata" in roles
    assert "section_heading" in roles

    sheet = sheet_from_dict(
        {
            "title": "t",
            "warnings": [],
            "asset_refs": [],
            "sections": [
                {
                    "title": "乙部 結構題 (50分)",
                    "declared_total": "50",
                    "computed_total": "2",
                    "mcq": None,
                    "questions": [
                        {
                            "label": "Q1",
                            "answer": [],
                            "answer_content": [],
                            "marks": None,
                            "children": [
                                {
                                    "label": "(a)",
                                    "answer": ["reviewed"],
                                    "answer_content": [
                                        {"kind": "paragraph", "text": "reviewed"},
                                        {"kind": "table", "rows": [["new left", "new right"]]},
                                    ],
                                    "marks": "2",
                                    "children": [],
                                    "has_non_text_content": False,
                                }
                            ],
                            "has_non_text_content": False,
                        }
                    ],
                    "standalone_non_text": False,
                }
            ],
        }
    )
    profile = RenderTemplateProfile(
        school_name="",
        logo_asset_id=None,
        config=_render_config("{{school_name}}", "{{document_type}}", ["{{school_name}}"]),
        layout_blueprint=draft.layout_blueprint,
        source_docx=source,
    )
    result = render_answer_sheet(
        sheet,
        profile,
        DocumentMetadata(
            school_name="Current school",
            academic_year="2024",
            exam_name="E",
            level="L",
            subject="B",
            document_type="Answer",
        ),
        {},
        lambda _: b"",
    )
    assert result.docx is not None, result.validation
    rendered = Document(BytesIO(result.docx))
    assert rendered.sections[0].header.paragraphs[0].alignment == WD_ALIGN_PARAGRAPH.RIGHT
    assert rendered.sections[0].footer.paragraphs[0].alignment == WD_ALIGN_PARAGRAPH.LEFT
    assert next(p for p in rendered.paragraphs if p.text == "Current school").alignment == WD_ALIGN_PARAGRAPH.RIGHT
    assert next(p for p in rendered.paragraphs if p.text == "乙部 結構題 (50分)").alignment == WD_ALIGN_PARAGRAPH.RIGHT
    answer_table = rendered.tables[0]
    assert answer_table.cell(0, 0).paragraphs[0].alignment == WD_ALIGN_PARAGRAPH.RIGHT


def test_renderer_reuses_source_tabs_and_does_not_invent_parent_total() -> None:
    source = _source()
    draft = import_template_docx(source)
    # This source root visibly has a total; override the source-derived signal to
    # model Sample (C), which has no parent total, while retaining its right tabs.
    blueprint = draft.layout_blueprint
    blueprint["parent_totals_by_depth"]["0"] = False
    sheet = sheet_from_dict({
        "title":"t", "warnings":[], "asset_refs":[],
        "sections":[{"title":"乙部 結構題 (50分)","declared_total":"50","computed_total":"51","mcq":None,
        "questions":[{"label":"Q1","answer":[],"answer_content":[],"marks":None,"children":[
            {"label":"(a)","answer":["reviewed answer"],"answer_content":[{"kind":"paragraph","text":"reviewed answer"}],"marks":"2","children":[],"has_non_text_content":False},
            {"label":"(b)","answer":["another"],"answer_content":[{"kind":"paragraph","text":"another"}],"marks":"4","children":[],"has_non_text_content":False},
        ],"has_non_text_content":False}],"standalone_non_text":False}],
    })
    profile = RenderTemplateProfile(
        school_name="",
        logo_asset_id=None,
        config=_render_config("", "", ["{{school_name}}"]),
        layout_blueprint=blueprint,
        source_docx=source,
    )
    result = render_answer_sheet(sheet, profile, DocumentMetadata(school_name="S", academic_year="2024", exam_name="E", level="L", subject="B", document_type="A"), {}, lambda _: b"")
    assert result.docx is not None, result.validation
    doc = Document(BytesIO(result.docx))
    q1 = next(p for p in doc.paragraphs if p.text.startswith("Q1"))
    sub = next(p for p in doc.paragraphs if p.text.startswith("(a)"))
    assert "(6" not in q1.text
    assert "\t" + "reviewed answer" + "\t(2 marks)" in sub.text
    assert abs(q1.paragraph_format.left_indent.mm - 4) < 0.01
    assert abs(sub.paragraph_format.left_indent.mm - 8) < 0.01
    assert "source answer must not be cloned" not in "\n".join(p.text for p in doc.paragraphs)
    with ZipFile(BytesIO(result.docx)) as package:
        xml = package.read("word/document.xml")
        assert b"w:tabs" in xml
