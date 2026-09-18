Status: ready-for-agent

# Marks, Snapshots, and Import Fidelity (Tier 1)

The first implementation tier of the marks-truth and reproducibility model. Governed by `CONTEXT.md` and ADR-0002 (marks truth) / ADR-0003 (immutability & reproducibility).

## Problem Statement

A teacher composing a Hong Kong exam paper needs the assembled paper to carry the correct marks, keep the content they already approved stable, and never lose content during import. Today, scoring truth is wrong for real papers, and content changes silently:

- Marks live as a single question-level value, so per-sub-part marks (e.g. `Q1(a)(ii) = 2`) are never structural — the printed total cannot be derived from them and is frequently wrong for real multi-part questions.
- Papers hold live references to library questions, so editing a reusable question later silently mutates every already-assembled paper, breaking reproducibility.
- Import silently fabricates data when it fails to parse (e.g. a mark defaults to `0`, a lossy `.doc` conversion drops answer text) with no signal to the teacher that content was lost or misread.

## Solution

Make scoring truth derivable from leaf marks, freeze paper content at the moment a question is added (snapshot), and make import explicit about the evidence it found and the gaps it couldn't resolve — so nothing is fabricated and nothing is silently discarded.

## User Stories

1. As a teacher, I want a mark to attach to the smallest sub-part that actually carries it, so that `Q1(a)(ii) = 2` is captured structurally rather than living on as plain text.
2. As a teacher, I want a standalone question with no sub-parts to carry its own mark directly, so that simple (e.g. multiple-choice) questions score correctly under the same rule as multi-part ones.
3. As a teacher, I want a question that has sub-parts to have its total computed as the sum of its sub-parts, so I never have to keep a parent total manually in sync with its children.
4. As a teacher, I want the paper's total marks to always equal the sum of every leaf mark, so the value printed on the paper is trustworthy.
5. As a teacher, I want the system to reject a node that has children *and* its own authoritative mark, so double counting is impossible rather than merely unlikely.
6. As a teacher, I want a question's marks to stay consistent when I reuse it across papers, so totals do not drift between otherwise identical papers.
7. As a teacher, when I add a question to a paper, I want the paper to take a snapshot of that question's content, so that editing the library question later does not change my already-assembled paper.
8. As a teacher, I want a paper to record which source question each snapshot came from, so I can trace provenance of what's on the paper.
9. As a teacher, when I edit a question in the library, I want an existing paper to keep showing the version I had when I assembled it, so assembled papers are reproducible.
10. As a teacher, when I import a document that states marks, I want those stated values preserved as declared evidence, so a later disagreement can be surfaced for my review.
11. As a teacher, when the total stated in my source disagrees with the computed total, I want the system to flag it, so I review it before trusting the output.
12. As a teacher, when the parser cannot reliably map some content — text, a marks annotation, or a structural pattern — I want that raw fragment preserved with a review flag, so it is never silently dropped.
13. As a teacher, I want "needs review" to be distinct from "declared marks were captured", so I can tell a clean parse from one the system was unsure about.
14. As a teacher, I want import never to fabricate a mark of `0` merely because it failed to detect one, so I am not misled by data the parser invented.
15. As a teacher, when a legacy `.doc` conversion is lossy, I want to be told it was lossy and flagged for review, rather than handed a clean-looking paper with missing content.
16. As a teacher, I want the preview and the exported document to show the same scoring truth, so the preview never recomputes totals differently from the export.
17. As a teacher, I want sub-part marks to render in the place my template specifies (right / inline / below), so the output matches my school's layout.
18. As a teacher, when I reorder questions in a paper, I want the total marks to remain correct without me recounting by hand.
19. As a teacher, when a parent or section subtotal is displayed, I want it to be the sum of its descendants and never double count its own value, so every subtotal is consistent with the total.

## Implementation Decisions

- **Leaf marks.** Any content node that can be a leaf carries an authoritative `marks` value: a childless question root is a leaf and may carry marks, and a nested sub-question that has no children is also a leaf and may carry marks.
- **Ancestors are computed only.** A node with children never holds an authoritative mark; its total is the sum of its descendant leaf marks. Aggregation is the single source of `computed_total_marks`.
- **Non-leaf marks are invalid.** The content schema rejects a node that has children *and* an authoritative mark, at validation time — not just by "happening not to count it" during aggregation.
- **Four distinct concepts, not one merged flag.** `declared_marks` (what the source stated, evidence only), `computed_marks` (leaf aggregation, the truth), `validation issue` (raised when a declared value disagrees with the computed value), and `needs_review` (the parser could not reliably map content, or content may be lost, or a validation issue needs a human) are treated as separate things.
- **No fabricated marks.** When the parser fails to detect a mark, it leaves it absent/null and flags `needs_review`; it never writes `0`.
- **Declared evidence at any level.** A stated value is preserved wherever the source states it (paper total, section subtotal, question subtotal, sub-part), as evidence only, never feeding computation. A question-level `[4 marks]` sitting above `(a)=2, (b)=2` is recorded as declared evidence, not as the computed answer.
- **Preserve unmappable source.** The import path retains enough raw source evidence (fragment/reference) for anything it cannot reliably map, and flags it for review, rather than dropping it.
- **Snapshot on add-to-paper.** Adding a question to a paper deep-copies its content at that moment; the paper's read and render paths read the snapshot, never re-dereferencing the live library question as the source of truth. Future edits to the source question do not mutate an existing paper.
- **Provenance, Tier 1 shape.** The snapshot records `source_question_id` for traceability; content hashing, formal revisions, and re-pull are explicitly deferred (Tier 2).
- **Remove dual-truth fields.** The single question-level `marks` field and the paper-level `marks_override` are removed and migrated into the leaf representation (per ADR-0002).
- **Renderer boundary.** The renderer projects an already-decided content tree — leaf marks, computed aggregates, and numbering — onto DOCX only; it performs no scoring-truth computation of its own.
- **Pure traversal, not a locked module.** Leaf detection, aggregation, computed totals, and numbering traversal live as pure, persistence-free logic behind the existing service seam. Numbering and marks share the traversal today; a future split into separate modules must be a non-breaking refactor, not a spec change.

## Testing Decisions

- Test external behavior only (correctness of marks, snapshots, and review flags), not internal implementation details.
- **Pure domain seam** — leaf detection, ancestor aggregation, `computed_total_marks`, and numbering traversal, tested unit-level with no DB or I/O (prior art: the existing numbering unit tests).
- **Content schema seam** — every leaf-capable node accepts marks; a node with children *and* an authoritative mark is rejected (prior art: existing content-schema validation tests).
- **Renderer seam** — fixture/golden DOCX tests that cover a standalone leaf, nested leaves, a parent subtotal that does not double count, and the sub-part numbering structure (prior art: existing renderer fixture/golden tests).
- **Import seam** — declared evidence is preserved, unmappable source fragments are preserved and flagged, `needs_review` is set where the parse is unreliable, and no `0` mark is fabricated (prior art: existing template-import and question-ingest tests).
- **Paper API seam** — adding a question materializes an independent snapshot, and a subsequent edit to the source question does not change the paper (prior art: existing papers API tests).
- **Validation seam** — a declared-vs-computed disagreement produces a basic validation issue in the simplest form Tier 1 requires.
- Add a regression test for "reordering questions keeps `computed_total_marks` correct" and "the preview and export agree on the total".

## Out of Scope

Everything deferred to Tier 2 per ADR-0003: content-hash asset revisions, immutable `TemplateRevision`, source-update / re-pull (including three-way merge), final-export blocking, and a full audit/resolution workflow. Also out of scope for this spec: the `NumberingPattern` and `numbering_scope` refactor in ADR-0001 (a companion spec); CJK numeral rendering (`cjk` / `cjk_upper` / `jia_yi`); and OCR/PDF extraction of question sets.

## Further Notes

- The numbering-model work is governed by ADR-0001 and should be specified separately; this spec must not regress existing numbering while the marks refactor touches the shared traversal.
- The three spec-detail defaults not yet decided — validation-issue severity taxonomy, how an unrecoverable-content loss may be acknowledged, and the exact migration steps for the legacy `marks` / `marks_override` data — should be resolved at implementation time and recorded, not left implicit.
- Where a decision in this spec could be read as contradicting an ADR, the ADR wins; reopen the ADR rather than silently overriding it.