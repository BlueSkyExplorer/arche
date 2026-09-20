# 02: Document parsing / layout extraction layer

**What to build:** A `DocumentParser` interface that turns PDF/DOCX/image into
normalized `DocumentBlock[]` with page + bbox + source text, keeping layout
metadata (`LayoutReference`) separate from content.

**Blocked by:** 01.

**Status:** ready-for-agent

- [ ] `DocumentBlock` (or reuse `ContentBlock`) is produced by a
      `DocumentParser` protocol, independent of format.
- [ ] DOCX parser: paragraphs, headings, lists, tables, images, answer-space,
      page estimation, font/size/bold/alignment into `LayoutReference`.
- [ ] PDF parser: text + layout via a deterministic extractor (pdftotext /
      pypdf / pdfplumber), page + bbox per block.
- [ ] Image parser: OCR (e.g. tesseract) producing text blocks + detected
      figures; low-confidence OCR flags `needs_review`.
- [ ] Cross-page reconciliation input: every block carries its page so the
      semantic layer can reattach a question that spans pages.
- [ ] Tests: a DOCX fixture and a PDF fixture round-trip into ordered blocks
      with correct page/bbox/source text.
