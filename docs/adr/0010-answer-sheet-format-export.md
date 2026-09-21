---
status: accepted
date: 2026-09-20
---

# Answer-sheet formatting and export uses semantic and immutable snapshots

Completed answer-sheet imports are formatted directly from
`ExamImport.reviewed_answer_sheet_json`. They are not materialized into the
Question Library and are not converted into `Paper` objects. The answer sheet
controls **what** is rendered; a validated `TemplateProfile` controls **how** it
is rendered. Rendering is deterministic and never calls an LLM or edits the
uploaded Word document.

## Content model

`AnsNode.answer` remains readable for existing rows. New extraction also writes
typed `answer_content` blocks: paragraphs, structured tables, image references,
and explicit unsupported blocks. Table cell structure is retained by the DOCX
parser. Relationship-backed images carry their exact `local_id`. Grouped Word
drawings produced by legacy `.doc` conversion are deterministically rasterized
through LibreOffice and mapped only when drawing order and non-text cell order
match exactly. An absent or ambiguous asset becomes a blocking render issue;
OCR and inferred replacement content are forbidden.

## Rendering and validation

The renderer accepts the reviewed answer-sheet snapshot, an immutable template
configuration/version snapshot, its immutable source DOCX artifact reference
(SHA-256 verified when loaded), content-free source-derived OOXML layout
blueprints, and per-document `DocumentMetadata`. The source DOCX is never text
replaced: renderer starts from its package to preserve styles, section/page
setup, headers/footers, and other document primitives, clears source content,
and injects only the reviewed semantic tree. Blueprints retain no teacher
answer text; they carry only paragraph/run/table primitives (`pPr`, `rPr`,
tabs, indents, spacing, alignment, `tblPr`, `tblGrid`, row/cell properties).
Metadata values remain per document. Template metadata/header/footer strings may use the
validated placeholders `school_name`, `academic_year`, `exam_name`, `level`,
`subject`, and `document_type`. Additive answer-sheet layout settings control
MCQ columns, hierarchy indentation/parent totals, image width, and table header
repetition. Existing template profiles receive validated defaults.

Before a DOCX is stored, validation accounts for every section, MCQ item,
question node, leaf, paragraph, table, and image. Missing assets, detached or
unsupported non-text content, empty tables, and authoritative marks on parent
nodes block export. Declared/computed mismatches and extraction warnings remain
visible but do not change leaf marks and do not block when no content would be
lost.

## Audit and authorization

Every preview and export creates an `AnswerSheetExport` record containing the
workspace/import/template identities, reviewed semantic snapshot, template
version and full configuration snapshot, metadata snapshot, validation result,
status, and private storage key. This makes old output reproducible after a
Template Profile changes. All lookups are workspace-scoped; private storage
keys are not returned by the new API.

Generation is synchronous behind a service boundary so it can later move to a
worker without changing the API or renderer.

## Consequences

- Approval means durable completion, not Question materialization; completed
  review is read-only.
- Browser preview is an inspectable approximation. The generated DOCX remains
  the fidelity artifact.
- Preview records also store DOCX output for audit, rather than creating
  untracked temporary files.
- PDF answer-sheet output and arbitrary OOXML shape copying remain out of scope.
