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


def test_renderer_chains_ancestor_labels_when_source_evidences_tab_chain() -> None:
    # (b) + (i) + answer + marks on ONE logical line, as Sample (C) evidences.
    source_document = Document()
    chained = source_document.add_paragraph("(b)\t(i)\t組織液\t(1分)")
    chained.paragraph_format.left_indent = Mm(8)
    chained.paragraph_format.tab_stops.add_tab_stop(Mm(160), WD_TAB_ALIGNMENT.RIGHT)
    doc2 = source_document.add_paragraph("Q4.\t(b)\tanswer\t(1分)")
    doc2.paragraph_format.tab_stops.add_tab_stop(Mm(160), WD_TAB_ALIGNMENT.RIGHT)
    raw = BytesIO()
    source_document.save(raw)
    source = raw.getvalue()
    draft = import_template_docx(source)
    blueprint = draft.layout_blueprint
    # Source shows one same-line chain record for the sub+subsub+answer+marks line.
    chains = blueprint.get("label_chains") or {}
    assert chains, "blueprint must capture the same-line label chain evidence"

    sheet = sheet_from_dict({
        "title":"t", "warnings":[], "asset_refs":[],
        "sections":[{"title":"乙部 結構題 (50分)","declared_total":"50","computed_total":"1","mcq":None,
        "questions":[{"label":"Q4","answer":[],"answer_content":[],"marks":None,"children":[
            {"label":"(b)","answer":[],"answer_content":[],"marks":None,"children":[
                {"label":"(i)","answer":["組織液"],"answer_content":[
                    {"kind":"paragraph","text":"組織液","marks":"1","mark_raw":"(1分)"},
                ],"marks":"1","children":[],"has_non_text_content":False},
            ],"has_non_text_content":False},
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
    line = next(p.text for p in doc.paragraphs if "組織液" in p.text)
    # one logical line: (b) (i) 組織液 (1分)
    assert line.startswith("(b)\t(i)\t組織液")
    assert line.endswith("(1 marks)")
    # the (b) and (i) labels must NOT be emitted as separate paragraphs
    assert not any(t.strip() == "(b)" for t in (p.text for p in doc.paragraphs))
    assert not any(t.strip() == "(i)" for t in (p.text for p in doc.paragraphs))


def test_renderer_emits_per_block_marking_points_not_aggregate() -> None:
    # (a) 二氧化碳 (1分) / 尿素 (1分) -> each paragraph carries its own right-tab mark
    source = _source()
    draft = import_template_docx(source)
    blueprint = draft.layout_blueprint
    blueprint["parent_totals_by_depth"]["0"] = False
    sheet = sheet_from_dict({
        "title":"t", "warnings":[], "asset_refs":[],
        "sections":[{"title":"乙部 結構題 (50分)","declared_total":"50","computed_total":"2","mcq":None,
        "questions":[{"label":"Q1","answer":[],"answer_content":[],"marks":None,"children":[
            {"label":"(a)","answer":["二氧化碳","尿素"],"answer_content":[
                {"kind":"paragraph","text":"二氧化碳","marks":"1","mark_raw":"(1分)"},
                {"kind":"paragraph","text":"尿素","marks":"1","mark_raw":"(1分)"},
            ],"marks":"2","children":[],"has_non_text_content":False},
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
    texts = [p.text for p in doc.paragraphs]
    co2 = next(t for t in texts if t.endswith("\t(1 marks)") and "二氧化碳" in t)
    urea = next(t for t in texts if t.endswith("\t(1 marks)") and "尿素" in t)
    assert "二氧化碳" in co2 and "\t" in co2
    assert "尿素" in urea and "\t" in urea
    # no aggregate "(2 marks)" for the leaf
    assert not any("(2 marks)" in t for t in texts)
    # the label line itself carries no aggregate marks either
    label = next(t for t in texts if t.startswith("(a)"))
    assert "二氧化碳" not in label or label.count("\t") == 0 or "marks" not in label


def test_renderer_keeps_question_label_with_first_content_for_pagination() -> None:
    # Source evidences keepNext on question label paragraphs; renderer must
    # apply keep_with_next so a label is never orphaned by a page break.
    source_document = Document()
    root = source_document.add_paragraph("Q1")
    root.paragraph_format.keep_with_next = True
    sub = source_document.add_paragraph("(a)\tformat answer\t(2分)")
    sub.paragraph_format.keep_with_next = True
    sub.paragraph_format.tab_stops.add_tab_stop(Mm(160), WD_TAB_ALIGNMENT.RIGHT)
    raw = BytesIO()
    source_document.save(raw)
    source = raw.getvalue()
    draft = import_template_docx(source)
    blueprint = draft.layout_blueprint
    blueprint["parent_totals_by_depth"]["0"] = False

    sheet = sheet_from_dict({
        "title":"t","warnings":[],"asset_refs":[],
        "sections":[{"title":"乙部 結構題 (50分)","declared_total":"50","computed_total":"2","mcq":None,
        "questions":[{"label":"Q3","answer":[],"answer_content":[],"marks":None,"children":[
            {"label":"(a)","answer":["柱頭呈羽狀"],"answer_content":[
                {"kind":"paragraph","text":"柱頭呈羽狀","marks":"1","mark_raw":"(1分)"},
            ],"marks":"1","children":[],"has_non_text_content":False},
        ],"has_non_text_content":False}],"standalone_non_text":False}],
    })
    profile = RenderTemplateProfile(
        school_name="", logo_asset_id=None,
        config=_render_config("", "", ["{{school_name}}"]),
        layout_blueprint=blueprint, source_docx=source,
    )
    result = render_answer_sheet(sheet, profile, DocumentMetadata(school_name="S",academic_year="2024",exam_name="E",level="L",subject="B",document_type="A"), {}, lambda _: b"")
    assert result.docx is not None, result.validation
    doc = Document(BytesIO(result.docx))
    q3 = next(p for p in doc.paragraphs if p.text.startswith("Q3"))
    assert q3.paragraph_format.keep_with_next is True


def test_mcq_exact_content_survives_to_rendered_docx() -> None:
    source = _source()
    draft = import_template_docx(source)
    blueprint = draft.layout_blueprint
    blueprint["parent_totals_by_depth"]["0"] = False
    mcq_pairs = [
        (str(n), a)
        for n, a in zip(range(1, 31), "ABCD" * 7 + "AB", strict=True)
    ]
    sheet = sheet_from_dict({
        "title":"t","warnings":[],"asset_refs":[],
        "sections":[{"title":"甲部 多項選擇題 (30分)","declared_total":"30","computed_total":None,
        "mcq":mcq_pairs,"questions":[],"standalone_non_text":False}],
    })
    profile = RenderTemplateProfile(
        school_name="", logo_asset_id=None,
        config=_render_config("", "", ["{{school_name}}"]),
        layout_blueprint=blueprint, source_docx=source,
    )
    result = render_answer_sheet(sheet, profile, DocumentMetadata(school_name="S",academic_year="2024",exam_name="E",level="L",subject="B",document_type="A"), {}, lambda _: b"")
    assert result.docx is not None, result.validation
    doc = Document(BytesIO(result.docx))
    rendered: list[tuple[str, str]] = []
    for table in doc.tables:
        rows = table.rows
        columns = len(rows[0].cells) // 2
        row_count = len(rows) - 1
        for row in range(row_count):
            for column in range(columns):
                index = row + column * row_count
                if index >= len(mcq_pairs):
                    continue
                q = table.cell(row + 1, column * 2).text.strip()
                a = table.cell(row + 1, column * 2 + 1).text.strip()
                if q.isdigit() and a:
                    rendered.append((q, a))
    # Visual column-pair layout reorders rows; semantic order must survive.
    assert len(rendered) == 30
    assert sorted(rendered, key=lambda pair: int(pair[0])) == mcq_pairs


def test_export_xml_has_separate_right_tab_mark_runs_per_marking_point() -> None:
    # Export regression: two marking points -> two right-tab mark runs,
    # NOT one aggregate "(2 marks)" line (H requirement).
    source = _source()
    draft = import_template_docx(source)
    blueprint = draft.layout_blueprint
    blueprint["parent_totals_by_depth"]["0"] = False
    sheet = sheet_from_dict({
        "title":"t","warnings":[],"asset_refs":[],
        "sections":[{"title":"乙部 結構題 (50分)","declared_total":"50","computed_total":"2","mcq":None,
        "questions":[{"label":"Q1","answer":[],"answer_content":[],"marks":None,"children":[
            {"label":"(a)","answer":["二氧化碳","尿素"],"answer_content":[
                {"kind":"paragraph","text":"二氧化碳","marks":"1","mark_raw":"(1分)"},
                {"kind":"paragraph","text":"尿素","marks":"1","mark_raw":"(1分)"},
            ],"marks":"2","children":[],"has_non_text_content":False},
        ],"has_non_text_content":False}],"standalone_non_text":False}],
    })
    profile = RenderTemplateProfile(
        school_name="", logo_asset_id=None,
        config=_render_config("", "", ["{{school_name}}"]),
        layout_blueprint=blueprint, source_docx=source,
    )
    result = render_answer_sheet(sheet, profile, DocumentMetadata(school_name="S",academic_year="2024",exam_name="E",level="L",subject="B",document_type="A"), {}, lambda _: b"")
    assert result.docx is not None, result.validation
    with ZipFile(BytesIO(result.docx)) as package:
        xml = package.read("word/document.xml").decode()
    import re as _re

    marked_paragraphs = _re.findall(r"<w:p\b[^>]*>.*?</w:p>", xml, _re.DOTALL)
    tab_mark = [
        p
        for p in marked_paragraphs
        if "<w:tab/>" in p and "(1 marks)" in p and ("二氧化碳" in p or "尿素" in p)
    ]
    assert len(tab_mark) == 2
    assert "(2 marks)" not in xml
