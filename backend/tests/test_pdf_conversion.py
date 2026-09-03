from pathlib import Path

import pytest

from app.core.config import Settings
from app.services.exports import _convert_pdf


def test_broken_libreoffice_binary_is_controlled(tmp_path: Path) -> None:
    broken = tmp_path / "broken-soffice"
    broken.write_text("#!/bin/sh\nexit 9\n")
    broken.chmod(0o755)
    settings = Settings(LIBREOFFICE_BIN=str(broken), EXPORT_MAX_PDF_TIMEOUT_S=2)
    with pytest.raises(RuntimeError, match="PDF conversion failed"):
        _convert_pdf(b"not-a-docx", settings)
