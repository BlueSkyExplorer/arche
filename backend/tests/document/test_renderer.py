from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from docx import Document

from app.document.renderer import render_paper
from tests.document.fixture import FIXTURES, IMAGE_ID, paper, profile

GOLDENS = Path(__file__).parent / "goldens"


def _part(docx: bytes, name: str) -> bytes:
    with ZipFile(BytesIO(docx)) as archive:
        return archive.read(name)


def _assert_golden(name: str, actual: bytes) -> None:
    path = GOLDENS / name
    if os.getenv("REGEN_GOLDEN") == "1":
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(actual)
    assert actual == path.read_bytes()


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
