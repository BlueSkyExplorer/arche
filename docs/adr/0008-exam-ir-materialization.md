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

**C — review/debug metadata (preserved on the draft; DB persistence deferred)**

- *Source evidence* (block id / page / bbox / source text / confidence) is now
  carried on `QuestionIngestDraft.source_evidence` (per-block, content order),
  and *extraction metadata* (extractor/provider/model/schema/warnings) on
  `QuestionIngestDraft.extraction_meta` — so the materializer no longer discards
  it. Persisting it on `Question` is a deferred additive migration (decision B:
  a durable import/extraction record), not required for question domain truth.
- `DeclaredMarkEvidence.source` (provenance) is still dropped — the draft
  `DeclaredMark` has no provenance field. A later additive field covers it.

None of these require a DB change now; each C item would be a later additive
migration with explicit backfill semantics.

## Marks invariant

The materializer does not re-derive marks — it copies `own_marks` straight
through: a known leaf → its value; an unknown leaf → `None` (the draft and the
content tree both carry `None`, never 0); a non-leaf → `None`, with the total
computed from leaf marks by the existing `computed_marks`. The declared subtotal
is carried only as `declared_marks` evidence.

## Review-state mapping

`ValidationIssue.severity` already distinguishes the three classes, and the
materializer maps them onto the draft without re-deriving validator semantics:

- `blocking` → `needs_review=True`, issue string prefixed `blocking: …` (the
  caller must not auto-persist as clean).
- `warning` → `needs_review=True`, issue string prefixed `warning: …`.
- `info` → `needs_review=False`, issue string prefixed `info: …`.

Unresolved image assets are emitted as `blocking` (a correctness-critical missing
asset is never silently dropped — it blocks clean auto-persist).

## Error policy

The materializer is not catch-all-and-continue: an unsupported `ContentBlock`
kind degrades to a paragraph (text preserved, loss documented); a missing image
asset is flagged `blocking` + `needs_review`; an invalid hierarchy (non-leaf with
`own_marks`) is rejected at IR construction, before materialization. Correctness
issues fail explicitly; reviewable ambiguity is preserved and marked.

## Round-trip detection

A test-only `_assert_round_trip(document, drafts)` helper compares the
materialized subtree signature (labels + `own_marks` in preorder) against the
Exam IR, plus content order and asset identity, so the materializer cannot
silently drop labels, hierarchy, unknown marks, or asset references.

## Consequences

- New `app/exam/materialization/materializer.py` (pure function).
- `ExamDocument -> QuestionIngestDraft` is testable in isolation; the existing
  `QuestionIngestDraft -> QuestionCreate -> Question` path is unchanged.
- Ticket 05 does not switch production ingest; wiring the extractor →
  materializer → persistence route is a later integration decision.
