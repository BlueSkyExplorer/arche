"""Template-import service + endpoint tests.

Pure-function tests need no DB; endpoint tests use the api_client fixture
(marked ``@pytest.mark.db`` like the rest of the suite).
"""
from pathlib import Path

import pytest

from app.services.template_import import import_template_docx

FIXTURE_DIR = Path(__file__).parent / "fixtures"
DOCX_MIME = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


def _fixture_bytes() -> bytes:
    return (FIXTURE_DIR / "school_format.docx").read_bytes()


def test_import_maps_page_and_typography() -> None:
    draft = import_template_docx(_fixture_bytes())
    t = draft.profile
    assert t.page_config_json.size == "A4"
    assert t.page_config_json.margin_top_mm == 20
    assert t.page_config_json.margin_left_mm == 20
    assert t.typography_config_json.chinese_font == "Noto Sans CJK"
    assert t.typography_config_json.latin_font == "Liberation Serif"
    assert t.typography_config_json.base_font_size_pt == 12
    assert t.header_config_json.text == "ST. MARY'S COLLEGE"
    assert t.footer_config_json.page_numbering is True


def test_import_reports_confidence_and_defaults() -> None:
    draft = import_template_docx(_fixture_bytes())
    assert "numbering_config_json" in draft.confidence
    assert 0 <= draft.confidence["numbering_config_json"] <= 1
    assert "question_style_config_json" in draft.confidence
    assert draft.profile.question_style_config_json.default_answer_lines >= 0


def test_import_rejects_empty_bytes() -> None:
    with pytest.raises(ValueError, match="empty"):
        import_template_docx(b"")


@pytest.mark.db
def test_import_endpoint_maps_and_returns_draft(api_client) -> None:
    response = api_client.post(
        "/api/v1/templates/import",
        files={"file": ("school_format.docx", _fixture_bytes(), DOCX_MIME)},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["profile"]["page_config_json"]["size"] == "A4"
    assert body["profile"]["typography_config_json"]["chinese_font"] == "Noto Sans CJK"
    assert body["profile"]["header_config_json"]["text"] == "ST. MARY'S COLLEGE"
    assert "confidence" in body
    assert "unmapped" in body


@pytest.mark.db
def test_import_endpoint_rejects_docm_and_bad_ext(api_client) -> None:
    bads = [
        ("tricks.docm", _fixture_bytes(), "application/octet-stream"),
        ("format.pdf", b"%PDF-1.7", "application/pdf"),
    ]
    for name, data, mime in bads:
        assert (
            api_client.post(
                "/api/v1/templates/import", files={"file": (name, data, mime)}
            ).status_code
            == 415
        )


@pytest.mark.db
def test_import_endpoint_accepts_doc(api_client) -> None:
    doc_bytes = (FIXTURE_DIR / "school_format.doc").read_bytes()
    response = api_client.post(
        "/api/v1/templates/import",
        files={"file": ("school_format.doc", doc_bytes, "application/msword")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["profile"]["page_config_json"]["size"] == "A4"