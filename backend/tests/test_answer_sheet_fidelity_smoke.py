"""Optional visual smoke for the real Sample (C) answer-sheet source.

Run only where the private fixture and LibreOffice are deliberately supplied:

    ARCHE_SAMPLE_C_ANS_DOC='/path/to/Sample (C) ANS.doc' \
      LIBREOFFICE_BIN=/path/to/soffice \
      uv run --with PyMuPDF pytest tests/test_answer_sheet_fidelity_smoke.py -q

The committed deterministic unit tests cover OOXML primitives.  This smoke
measures rendered PDF pages without adding a private teacher document to Git.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.core.config import Settings
from app.document.renderer import RenderTemplateProfile
from app.document.renderer.answer_sheet import render_answer_sheet
from app.exam.extraction.answer_sheet import extract_answer_sheet
from app.exam.parsing.base import parse_document
from app.schemas.answer_sheet_export import DocumentMetadata
from app.schemas.template_profile import TemplateProfileConfig
from app.services.doc_convert import convert_doc_to_docx
from app.services.exports import _convert_pdf
from app.services.template_import import import_template_docx


def _config_from_import() -> tuple[bytes, RenderTemplateProfile]:
    source_path = os.environ.get("ARCHE_SAMPLE_C_ANS_DOC")
    if not source_path:
        pytest.skip("Set ARCHE_SAMPLE_C_ANS_DOC to enable the private Sample (C) smoke")
    source = Path(source_path)
    if not source.is_file():
        pytest.skip("ARCHE_SAMPLE_C_ANS_DOC does not point to a readable file")
    libreoffice_bin = os.environ.get("LIBREOFFICE_BIN")
    if not libreoffice_bin or not Path(libreoffice_bin).is_file():
        pytest.skip("Set LIBREOFFICE_BIN to a working soffice binary")

    source_docx = convert_doc_to_docx(
        source.read_bytes(), Settings(libreoffice_bin=libreoffice_bin)
    )
    draft = import_template_docx(source_docx)
    config = TemplateProfileConfig.model_validate(
        {name: getattr(draft.profile, name) for name in TemplateProfileConfig.model_fields}
    )
    return source_docx, RenderTemplateProfile(
        school_name="",
        logo_asset_id=None,
        config=config,
        layout_blueprint=draft.layout_blueprint,
        source_docx=source_docx,
    )


def _mean_page_difference(source_pdf: bytes, rendered_pdf: bytes) -> list[float]:
    fitz = pytest.importorskip("fitz", reason="install PyMuPDF for PDF raster comparison")
    source = fitz.open(stream=source_pdf, filetype="pdf")
    rendered = fitz.open(stream=rendered_pdf, filetype="pdf")
    assert len(source) == len(rendered)
    differences: list[float] = []
    for source_page, rendered_page in zip(source, rendered, strict=True):
        source_pixels = source_page.get_pixmap(
            matrix=fitz.Matrix(1, 1), colorspace=fitz.csGRAY, alpha=False
        )
        rendered_pixels = rendered_page.get_pixmap(
            matrix=fitz.Matrix(1, 1), colorspace=fitz.csGRAY, alpha=False
        )
        assert len(source_pixels.samples) == len(rendered_pixels.samples)
        differences.append(
            sum(
                abs(left - right)
                for left, right in zip(
                    source_pixels.samples, rendered_pixels.samples, strict=True
                )
            )
            / (255 * len(source_pixels.samples))
        )
    return differences


@pytest.mark.libreoffice
def test_sample_c_layout_smoke_has_same_page_count_and_bounded_image_difference() -> None:
    source_docx, profile = _config_from_import()
    sheet = extract_answer_sheet(parse_document(source_docx, filename="Sample (C) ANS.docx"))
    assert profile.layout_blueprint["parent_totals_by_depth"]["0"] is False

    result = render_answer_sheet(
        sheet,
        profile,
        DocumentMetadata(
            school_name="余振強紀念中學",
            academic_year="2024-2025",
            exam_name="下學期考試",
            level="中四級",
            subject="生物科",
            document_type="參考答案",
        ),
        {},
        lambda _: b"",
    )
    assert result.docx is not None, result.validation

    settings = Settings(libreoffice_bin=os.environ["LIBREOFFICE_BIN"])
    differences = _mean_page_difference(
        _convert_pdf(source_docx, settings), _convert_pdf(result.docx, settings)
    )
    assert max(differences, default=0) <= 0.06
