# Glossary

Canonical domain vocabulary for Arche. Terms here are definitions only — no
implementation detail, no spec. Update this file the moment a term is resolved.

## Format document (格式文件)

Either of two accepted inputs that describe a school's paper format:

- **Blank template** — layout/typography/header/footer/numbering only, no
  question content.
- **Filled example paper** — a real, populated paper from which formatting must
  be extracted (content stripped, format kept).

Both become a review draft on import, never a trusted `Template Profile`
without teacher approval.

## Template Profile

A reusable school format definition. After import it is untrusted until the
teacher reviews and saves it.

## Template Revision

An immutable snapshot of a Template Profile's configuration. A new revision is
created when the configuration undergoes an actual semantic change; a revision
that has been referenced by a Paper is never edited in place.

## Question Snapshot

A copy of a `Question`'s content captured at the moment it is added to a
`Paper`. The paper stores `source_question_id` alongside the snapshot, so
provenance is preserved while edits to the source Question no longer mutate
already-assembled papers.

## Template config snapshot

The fully resolved template configuration captured on a `Paper` (and its
`Export`) at commit/export time. `template_version` is retained for
traceability; the snapshot is what makes an old paper reproducible after the
source template changes.

## Leaf mark / scoring node

Only a leaf node may carry an authoritative mark. A node with children is
always the sum of its descendant leaves and cannot hold its own `own_marks`. A
childless question (e.g. a multiple-choice item) is its own leaf, so its mark
sits on the question root. Ancestor totals are computed, never stored.

## computed_total_marks

The authoritative paper total: the sum of all scoring leaf marks. Always
derived, never a user-editable field.

## Declared marks (declared_total_marks / declared_subtotal)

A mark or subtotal stated in the source material (e.g. an imported
`Total: 100`, or a question-level `[4 marks]` over sub-parts worth 2+2).
Retained as validation evidence only, at whichever level the source states it.
When it disagrees with the computed value, the mismatch is flagged; declared
values never participate in computation.

## Asset revision (immutable asset)

An object stored under an immutable, content-addressed key (e.g. a content
hash). Replacing an image or logo creates a new revision rather than mutating
the old one, so a paper referencing an older revision keeps rendering
identically, while identical content is still deduplicated by hash.

## Source revision

A marker that identifies the version of a source Question a snapshot was taken
from, used to detect "the source has been updated since".

## Question Revision

An immutable version of a Question: `revision_number` (human-facing v1/v2/…)
plus `content_hash` (machine identity, change detection, dedup). A Paper
snapshot records `source_question_id`, `source_revision_id`, and
`source_content_hash`.

## Numbering pattern

A canonical, lossless description of how a counter is rendered:
`numeral_system` (`arabic` / `alpha_lower` / `alpha_upper` / `roman_lower` /
`roman_upper` / `cjk` / `cjk_upper` / `jia_yi`) plus `prefix`/`suffix`, or an
explicit `pattern` (e.g. `第{n}題`). Replaces the fixed per-level style enums.

## Numbering scope

Where the question counter resets: `continuous` (across sections) or
`per_section` (each section restarts at 1). A template setting, never hard-coded
in the renderer.

## Validation issue / resolution

A human-processed discrepancy surfaced during import or assembly (e.g. declared
vs computed marks). Resolution is an explicit acknowledgement
(e.g. `accepted_computed_value`) with a reason and actor — never silently
editing data to force agreement.

## Re-pull (apply latest)

An explicit, user-triggered action that brings a source Question's latest
content into a Paper's snapshot. It never happens automatically.

## Final / release export

An export state for a paper that is being issued to students. A mismatch
between declared and computed marks blocks this state until resolved, whereas a
draft export only annotates the unresolved issue.

## Import Review (needs_review)

The mechanism that surfaces low-confidence, unsupported, or lossy results
(missing marks, dropped text/images, unrecognised numbering) to the teacher
before anything is committed. Import must never silently produce a
looks-correct-but-incomplete paper.

## Lossy conversion

A source-format conversion (notably legacy `.doc` → `.docx`) that may drop
content. Lossy results are flagged `needs_review`, never reported as a clean
import. `.docx` is the canonical, first-class input format.

## Answer Sheet (AnsSheet)

A reviewed semantic answer key owned by an `ExamImport`. It contains sections,
MCQ answers, an arbitrary-depth answer hierarchy, leaf-only authoritative marks,
and typed answer content (paragraph/table/image). Approval marks durable
completion; it never creates Question Library entries.

## Answer-sheet export snapshot

An immutable audit record combining a reviewed AnsSheet snapshot, Template
Profile config/version snapshot, per-document metadata, render validation, and
the stored DOCX. It remains reproducible after the live template changes.
