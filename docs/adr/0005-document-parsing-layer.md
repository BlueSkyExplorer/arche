---
status: accepted
date: 2026-09-20
---

# Document parsing layer: format adapters behind a common block contract

The parsing layer (exam-import-pipeline ticket 02) must reduce PDF, DOCX, and
image input to a single provider-independent `DocumentBlock[]`, preserving
*what* is in the document, *where* it is, and its *reading order* — without any
question/marks semantics (that is tickets 03/04).

## Considered Options

### Option 1 — Format adapters behind a `DocumentParser` protocol (chosen)

Each source format is a native adapter (`DocxParser`, `PdfParser`, later
`ImageParser`/OCR) implementing the same protocol and emitting the same
`DocumentBlock[]` contract. A dispatcher picks the adapter by magic bytes.

- **Pros:** no lossy intermediate; DOCX keeps styles/images/tables natively, PDF
  keeps its text layer; parsers are independently testable and swappable; adding
  a format never touches the others or the callers.
- **Cons:** N parsers to maintain (one per format).

### Option 2 — Normalize to one format first (e.g. render DOCX→PDF, always parse PDF)

Convert everything to a canonical representation, then run a single parser.

- **Pros:** one parser to maintain.
- **Cons:** the conversion is itself lossy (DOCX heading styles, inline images,
  and tables degrade through a PDF render); adds a heavyweight runtime
  dependency (LibreOffice/Poppler) to the hot path; breaks the "format fidelity"
  requirement. Rejected.

## PDF library strategy

| library | text | bbox | tables | images | dependency weight | license |
|---|---|---|---|---|---|---|
| **pypdf** | ✓ | ✗ | ✗ | partial | pure-Python (light) | BSD |
| pdfplumber | ✓ | ✓ chars/words | ✓ | ✗ | pdfminer.six + Pillow (heavy) | MIT |
| PyMuPDF (`fitz`) | ✓ | ✓ | ✓ | ✓ | native wheel (heavy) | AGPL |
| pdftotext (Poppler) | ✓ | ✓ (`-bbox`) | ✗ | ✗ | system binary | GPL |

**Decision:** start with **pypdf** — it extracts the native text layer and page
count deterministically with a single pure-Python dependency and no system
binary. It cannot resolve bbox/tables/images, which is exactly the "missing
bbox" case the contract already models (`bbox=None`). The **pdfplumber** (or
PyMuPDF if AGPL is acceptable) upgrade path is reserved for when geometry/table
fidelity becomes a requirement; the `DocumentParser` boundary means that swap
touches only `PdfParser`.

## Decision

Option 1 with pypdf now and pdfplumber as the documented upgrade path for
layout-aware PDF extraction.

## Consequences

- New `app/exam/parsing/`: `blocks.py` (contract), `base.py` (protocol +
  dispatch), `docx_parser.py`, `pdf_parser.py`.
- DOCX has no absolute geometry without rendering → `page`/`bbox` are `None`;
  reading order is preserved via the `order` index.
- PDF text blocks carry `page` but `bbox=None`; scanned pages (no text layer)
  yield no blocks and set `needs_review` so downstream can route to OCR.
- OCR/image parsing is an unimplemented adapter behind the same protocol — no
  OCR binary or cloud provider is wired in this phase.
- The `DocumentBlock` reuses the Exam IR's `BBox`/`AssetReference`, so one
  geometry/asset vocabulary spans parsing → semantic extraction.
