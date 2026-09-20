# 02: Document parsing / layout extraction layer

**What to build:** A `DocumentParser` interface that turns PDF/DOCX/image into
normalized `DocumentBlock[]` with page + bbox + source text, keeping layout
metadata (`LayoutReference`) separate from content.

**Blocked by:** 01.

**Status:** done

## Implementation record

Implemented the parser boundary (no semantic extraction, no LLM):

- `app/exam/parsing/blocks.py` — `BlockKind` (text/heading/image/table/equation/
  caption/header/footer), `SourceReference`, `DocumentBlock`, `ParseResult`
  (+ raw image `assets`). Reuses IR `BBox`/`AssetReference`.
- `app/exam/parsing/base.py` — `DocumentParser` protocol, `ParseError` /
  `UnsupportedFormatError`, magic-byte `parse_document()` dispatch.
- `app/exam/parsing/docx_parser.py` — python-docx walk in reading order
  (paragraphs+tables interleaved) + headers/footers; detects heading style,
  OMML equation, inline/cell images, captions, tables. `page`/`bbox=None`.
- `app/exam/parsing/pdf_parser.py` — pypdf text layer, page-tagged, `bbox=None`;
  scanned pages flag `needs_review`.
- `tests/test_document_parsing.py` — 13 tests (DOCX kinds/reading order/heading/
  table/image/equation/header-footer/missing-bbox/malformed; PDF pages/scanned/
  malformed; dispatch/unsupported).
- `docs/adr/0005-document-parsing-layer.md` — architecture + library decision.

Deferred (later tickets): OCR/image adapter; pdfplumber layout-aware PDF
(bbox/tables); page estimation for DOCX.

- [x] `DocumentBlock` produced by a `DocumentParser` protocol, independent of format.
- [x] DOCX parser: paragraphs, headings, tables, images, equations, header/footer.
- [x] PDF parser: text layer + page tagging (layout-aware upgrade = pdfplumber, ADR-0005).
- [ ] Image/OCR parser — deferred (no OCR binary/cloud provider wired).
- [x] Every block carries its page (PDF) / order (DOCX) for cross-page reattachment.
- [x] Tests: DOCX + PDF fixtures round-trip into ordered blocks.
