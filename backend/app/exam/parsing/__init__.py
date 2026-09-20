"""Document parsing layer: format parsers that emit a common ``DocumentBlock[]``.

See ``blocks.py`` for the contract, ``base.py`` for the ``DocumentParser``
protocol + dispatch, and the per-format parsers for implementations. This layer
performs layout extraction only — no question/marks semantics.
"""

from app.exam.parsing.base import (
    DocumentParser,
    ParseError,
    UnsupportedFormatError,
    parse_document,
)
from app.exam.parsing.blocks import BlockKind, DocumentBlock, ParseResult, SourceReference
from app.exam.parsing.docx_parser import DocxParser
from app.exam.parsing.pdf_parser import PdfParser

__all__ = [
    "BlockKind",
    "DocumentBlock",
    "DocumentParser",
    "DocxParser",
    "ParseError",
    "ParseResult",
    "PdfParser",
    "SourceReference",
    "UnsupportedFormatError",
    "parse_document",
]
