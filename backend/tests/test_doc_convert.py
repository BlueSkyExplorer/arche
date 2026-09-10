"""Doc-conversion service tests (skip when LibreOffice is unavailable)."""
from pathlib import Path

import pytest

from app.core.config import Settings
from app.services.doc_convert import DocConversionError, convert_doc_to_docx
from app.services.template_import import import_template_docx

FIXTURE = Path(__file__).parent / "fixtures" / "school_format.doc"
SOFFICE = "/opt/data/libreoffice/bin/soffice-arche"

pytestmark = pytest.mark.skipif(
    not Path(SOFFICE).exists(), reason="LibreOffice wrapper not installed"
)


def _settings() -> Settings:
    return Settings(libreoffice_bin=SOFFICE, export_max_pdf_timeout_s=60)


def test_doc_converts_to_parseable_docx() -> None:
    docx = convert_doc_to_docx(FIXTURE.read_bytes(), _settings())
    assert docx.startswith(b"PK\x03\x04")
    draft = import_template_docx(docx)  # converted output must parse like a native .docx
    assert draft.profile.school_name == "ST. MARY'S COLLEGE"


def test_doc_conversion_rejects_empty() -> None:
    with pytest.raises(DocConversionError):
        convert_doc_to_docx(b"", _settings())