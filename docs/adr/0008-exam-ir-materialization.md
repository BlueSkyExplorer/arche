---
status: accepted
date: 2026-09-20
---

# Exam IR materialization: deterministic translation to the ingest DTO

Ticket 05 of the exam-import pipeline. `materialize_exam_document` translates a
validated `ExamDocument` into the existing ingest representation
(`QuestionIngestDraft`), one draft per top-level question. It is a pure function:
no LLM, no re-parsing, no re-detecting marks/numbering, no network, no DB, and no
knowledge of which extractor produced the document.

## Field-by-field mapping

| Exam IR | Persistence (QuestionIngestDraft / content_json) |
|---|---|
| `QuestionNode.label` (top level) | `internal_title` (fallback `"Question N"`) |
| `QuestionNode.label` (child) | `SubQuestionNode.attrs.label` |
| `QuestionNode.own_marks` (leaf) | `DocNode.marks` / `SubQuestionNode.attrs.marks` / draft `marks` |
| `QuestionNode.own_marks = None` | `None`/`NULL` — never coerced to 0 |
| `QuestionNode.children` (arbitrary depth) | nested `SubQuestionNode.content` |
| `DeclaredMarkEvidence` | `QuestionIngestDraft.declared_marks` (`value`/`raw_text`/`location`) |
| `ContentBlock.paragraph` | `ParagraphNode` |
| `ContentBlock.heading` | `HeadingNode` (level clamped 1..3) |
| `ContentBlock.image` | `ImageNode.attrs.asset_id` via `asset_id_for(local_id)` |
| `ContentBlock.table` (rows) | `TableNode` → `tableRow` → `tableCell` → paragraph |
| `ContentBlock.equation` / `list` / `answer_space` | `ParagraphNode` (text preserved — see gaps) |
| `ExamDocument.subject` / `level` | draft `subject` / `level` |
| `Section.title` | draft `source_note` |

## Representation gaps (classified)

**A — must solve for correctness**

- *Image asset resolution.* `content_json`'s `ImageNode` requires a UUID, but the
  IR references assets by `local_id`. Solved at the boundary: the materializer
  takes an injectable `asset_id_for(local_id) -> UUID`. Without it, an image block
  is flagged (`unresolved_image_asset` + `needs_review`), never silently dropped.

**B — no lossless representation, does not affect question domain truth**

- *Equation identity.* `content_json` has no equation node; the equation's text is
  preserved as a paragraph. The `equation` semantic is recoverable only by a
  future additive schema node.
- *List identity.* Same — falls back to a paragraph.
- *Heading level 4..6.* `HeadingNode` supports 1..3 only; deeper levels clamp to 3.
- *Sections.* The Question Library is flat; sections flatten into drafts, with the
  section title carried in `source_note`.
- *`answer_space`.* No dimension info in the IR; falls back to an empty paragraph.

**C — review/debug metadata, defer (additive migration if ever needed)**

- *Source evidence* (page / block id / bbox / source text / confidence) is not
  persisted on `Question` or `content_json`. `DeclaredMarkEvidence.source` is
  dropped (the draft `DeclaredMark` has no provenance field).
- *Extraction warnings / confidence* are surfaced on the draft (`needs_review`,
  `validation_issues`) but not persisted to `Question`.

None of these require a DB change now; each C item would be a later additive
migration.

## Marks invariant

The materializer does not re-derive marks — it copies `own_marks` straight
through: a known leaf → its value; an unknown leaf → `None` (the draft and the
content tree both carry `None`, never 0); a non-leaf → `None`, with the total
computed from leaf marks by the existing `computed_marks`. The declared subtotal
is carried only as `declared_marks` evidence.

## Consequences

- New `app/exam/materialization/materializer.py` (pure function).
- `ExamDocument -> QuestionIngestDraft` is testable in isolation; the existing
  `QuestionIngestDraft -> QuestionCreate -> Question` path is unchanged.
- Ticket 05 does not switch production ingest; wiring the extractor →
  materializer → persistence route is a later integration decision.
