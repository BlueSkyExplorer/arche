"""Parser interface + format dispatch.

Every source format (DOCX, PDF, image/OCR, …) implements ``DocumentParser`` and
emits the same ``ParseResult`` / ``DocumentBlock[]`` contract. The dispatcher
selects a parser by magic bytes (with filename/extension as a fallback hint), so
adding a format never changes the callers.
"""

from __future__ import annotations

from typing import Protocol

from app.exam.parsing.blocks import ParseResult


class ParseError(ValueError):
    """A document could not be parsed by the selected parser."""


class UnsupportedFormatError(ParseError):
    """No parser is registered for this input."""


class DocumentParser(Protocol):
    name: str

    def supports(self, content_type: str | None, filename: str | None) -> bool: ...

    def parse(self, data: bytes, source_name: str | None = None) -> ParseResult: ...


_ZIP_MAGIC = b"PK\x03\x04"
_PDF_MAGIC = b"%PDF"


def detect_format(data: bytes, filename: str | None = None) -> str:
    """Return a coarse format tag from magic bytes, falling back to the name."""
    if data[:4] == _ZIP_MAGIC:
        return "docx"
    if data[:4] == _PDF_MAGIC:
        return "pdf"
    name = (filename or "").lower()
    if name.endswith(".docx"):
        return "docx"
    if name.endswith(".pdf"):
        return "pdf"
    return "unknown"


def parse_document(
    data: bytes,
    *,
    content_type: str | None = None,
    filename: str | None = None,
) -> ParseResult:
    """Parse a document into ``DocumentBlock[]`` using the matching parser.

    Raises ``UnsupportedFormatError`` when the format is unknown, and
    ``ParseError`` when the selected parser cannot handle the bytes.
    """
    fmt = detect_format(data, filename)
    if fmt == "docx":
        from app.exam.parsing.docx_parser import DocxParser

        return DocxParser().parse(data, source_name=filename)
    if fmt == "pdf":
        from app.exam.parsing.pdf_parser import PdfParser

        return PdfParser().parse(data, source_name=filename)
    raise UnsupportedFormatError(f"unsupported document format: {fmt!r}")
