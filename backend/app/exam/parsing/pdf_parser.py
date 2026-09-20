"""PDF → ``DocumentBlock[]`` parser (text layer, via pypdf).

First deterministic slice: extracts the native text layer page by page in reading
order. It does not interpret layout beyond line order, and it does not resolve
image/table geometry — those are flagged as limitations for the layout-aware
upgrade (pdfplumber) rather than guessed.

Scanned pages (no text layer) yield no blocks and set ``needs_review`` so the
downstream can route them to OCR. Blocks carry ``page`` but ``bbox=None`` (the
documented "missing bbox" case).
"""

from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader

from app.exam.parsing.base import ParseError
from app.exam.parsing.blocks import BlockKind, DocumentBlock, ParseResult, SourceReference


class PdfParser:
    name = "pdf"

    def supports(self, content_type: str | None, filename: str | None) -> bool:
        name = (filename or "").lower()
        return name.endswith(".pdf") or content_type == "application/pdf"

    def parse(self, data: bytes, source_name: str | None = None) -> ParseResult:
        if not data or data[:4] != b"%PDF":
            raise ParseError("not a PDF (missing %PDF header)")
        try:
            reader = PdfReader(BytesIO(data))
        except Exception as exc:  # noqa: BLE001 - malformed input surfaces as ParseError
            raise ParseError(f"malformed PDF: {exc}") from exc

        blocks: list[DocumentBlock] = []
        order = 0
        warnings: list[str] = []
        scanned_pages = 0
        pages_with_images = 0

        for page_index, page in enumerate(reader.pages):
            page_no = page_index + 1
            text = page.extract_text() or ""
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            if not lines:
                scanned_pages += 1
            for line in lines:
                blocks.append(
                    DocumentBlock(
                        id=f"b{order:04d}",
                        page=page_no,
                        kind=BlockKind.TEXT,
                        text=line,
                        order=order,
                        source=SourceReference(file_name=source_name, page=page_no),
                    )
                )
                order += 1
            if getattr(page, "images", None):
                pages_with_images += 1

        if scanned_pages:
            warnings.append(
                f"{scanned_pages} page(s) have no text layer (scanned PDF — OCR required)"
            )
        if pages_with_images:
            warnings.append(
                f"{pages_with_images} page(s) contain embedded images whose position "
                "is not resolved by the text-layer parser"
            )

        return ParseResult(
            blocks=blocks,
            assets={},
            page_count=len(reader.pages),
            source_name=source_name,
            format="pdf",
            warnings=warnings,
            needs_review=scanned_pages > 0,
        )
