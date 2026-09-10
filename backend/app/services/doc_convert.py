"""Convert legacy .doc uploads to .docx via headless LibreOffice.

Reuses the same invocation shape as exports._convert_pdf. Conversion is
best-effort and deterministic; failures surface as controlled errors.
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path

from app.core.config import Settings


class DocConversionError(RuntimeError):
    """Raised when LibreOffice cannot convert an uploaded .doc."""


def _resolve_binary(settings: Settings) -> str:
    configured = settings.libreoffice_bin
    if Path(configured).exists():
        return configured
    if Path(configured).name == configured:
        found = shutil.which(configured)
        if found:
            return found
    raise DocConversionError("LibreOffice is unavailable")


def convert_doc_to_docx(data: bytes, settings: Settings) -> bytes:
    """Return .docx bytes for a legacy .doc payload (or raise DocConversionError)."""
    if not data:
        raise DocConversionError("empty document")
    binary = _resolve_binary(settings)
    with tempfile.TemporaryDirectory(prefix="arche-doc-") as directory:
        root = Path(directory)
        source = root / "input.doc"
        source.write_bytes(data)
        process = subprocess.Popen(
            [
                binary,
                "-env:UserInstallation=file:///tmp/arche-lo-profile",
                "--headless",
                "--convert-to",
                "docx",
                "--outdir",
                str(root),
                str(source),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=settings.export_max_pdf_timeout_s)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise DocConversionError("DOC conversion timed out") from None
        del stdout, stderr
        if process.returncode != 0:
            raise DocConversionError("DOC conversion failed")
        output = root / "input.docx"
        if not output.exists() or not output.read_bytes().startswith(b"PK\x03\x04"):
            raise DocConversionError("DOC conversion produced no valid DOCX")
        return output.read_bytes()