from __future__ import annotations

import os
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from docx import Document

from app.document.renderer import (
    PaperData,
    RenderQuestion,
    RenderSection,
    _format_marks,
    render_paper,
)
from app.schemas.content import DocNode
from tests.document.fixture import FIXTURES, IMAGE_ID, paper, profile
from tests.document.regenerate import update_golden

GOLDENS = Path(__file__).parent / "goldens"


def _part(docx: bytes, name: str) -> bytes:
    with ZipFile(BytesIO(docx)) as archive:
        return archive.read(name)


def _assert_golden(name: str, actual: bytes) -> None:
    path = GOLDENS / name
    if os.getenv("REGEN_GOLDEN") == "1":
        update_golden(path, actual)
    assert actual == path.read_bytes()


def _render_content(content: DocNode) -> bytes:
    question = RenderQuestion(
        id=paper().sections[0].questions[0].id,
        position=1,
        content=content,
        marks=Decimal("1"),
    )
    data = PaperData(
        title="Renderer edge case",
        sections=(RenderSection(title="Section", position=1, questions=(question,)),),
    )
    return render_paper(data, profile(), {IMAGE_ID: (FIXTURES / "tiny.png").read_bytes()})


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1", "(1 marks)"),
        ("2", "(2 marks)"),
        ("7", "(7 marks)"),
        ("10", "(10 marks)"),
        ("20", "(20 marks)"),
        ("100", "(100 marks)"),
        ("0.5", "(0.5 marks)"),
        ("2.50", "(2.5 marks)"),
        ("12.25", "(12.25 marks)"),
    ],
)
def test_format_marks_preserves_integer_zeros(value: str, expected: str) -> None:
    assert _format_marks(Decimal(value), "({marks} marks)") == expected


def test_default_profile_golden_and_wording_fidelity() -> None:
    output = render_paper(paper(), profile(), {IMAGE_ID: (FIXTURES / "tiny.png").read_bytes()})
    _assert_golden("default-document.xml", _part(output, "word/document.xml"))
    extracted = "\n".join(paragraph.text for paragraph in Document(BytesIO(output)).paragraphs)
    for wording in (
        "保留原文 Keep wording: ",
        "粗體",
        " italic",
        " underline",
        "第一小題",
        "Second part",
        "第三小題",
        "Ten-mark question",
        "(10 marks)",
        "Twenty-mark question",
        "(20 marks)",
    ):
        assert wording in extracted


def test_variant_profile_golden_proves_page_and_typography_config() -> None:
    output = render_paper(
        paper(), profile(variant=True), {IMAGE_ID: (FIXTURES / "tiny.png").read_bytes()}
    )
    _assert_golden("variant-document.xml", _part(output, "word/document.xml"))
    styles = _part(output, "word/styles.xml")
    assert b"Times New Roman" in styles
    assert b"PMingLiU" in styles


def test_render_is_byte_for_byte_deterministic() -> None:
    assets = {IMAGE_ID: (FIXTURES / "tiny.png").read_bytes()}
    first = render_paper(paper(), profile(), assets)
    second = render_paper(paper(), profile(), assets)
    assert _part(first, "word/document.xml") == _part(second, "word/document.xml")
    assert first == second


def test_camel_case_image_asset_is_embedded_in_document() -> None:
    image = (FIXTURES / "tiny.png").read_bytes()
    content = DocNode.model_validate(
        {
            "type": "doc",
            "content": [
                {"type": "image", "attrs": {"assetId": str(IMAGE_ID), "alt": None, "widthMm": 20}}
            ],
        }
    )
    rendered = _render_content(content)
    with ZipFile(BytesIO(rendered)) as archive:
        assert image in (
            archive.read(name) for name in archive.namelist() if name.startswith("word/media/")
        )
        assert b"r:embed" in archive.read("word/document.xml")


def test_blank_height_answer_space_is_rendered() -> None:
    rendered = _render_content(
        DocNode.model_validate(
            {
                "type": "doc",
                "content": [{"type": "answerSpace", "attrs": {"blankHeightMm": 12.5}}],
            }
        )
    )
    assert b'w:line="709"' in _part(rendered, "word/document.xml")


@pytest.mark.parametrize(
    "first_child",
    [
        {
            "type": "bulletList",
            "content": [
                {
                    "type": "listItem",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": "List first"}],
                        }
                    ],
                }
            ],
        },
        {
            "type": "table",
            "content": [
                {
                    "type": "tableRow",
                    "content": [
                        {
                            "type": "tableCell",
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [{"type": "text", "text": "Table first"}],
                                }
                            ],
                        }
                    ],
                }
            ],
        },
    ],
)
def test_sub_question_can_start_with_list_or_table(first_child: object) -> None:
    content = DocNode.model_validate(
        {
            "type": "doc",
            "content": [
                {
                    "type": "subQuestion",
                    "attrs": {"label": "(a)"},
                    "content": [first_child],
                }
            ],
        }
    )
    extracted = "\n".join(
        paragraph.text for paragraph in Document(BytesIO(_render_content(content))).paragraphs
    )
    assert "(a)" in extracted
