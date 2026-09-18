---
status: accepted
date: 2026-09-18
---

# Immutability & reproducibility: snapshots + immutable revisions

A Paper snapshots question content at the moment it is added, rather than
referencing the source Question live; the snapshot keeps `source_question_id`,
`source_revision_id`, and `source_content_hash` for provenance. Templates,
Questions, and Assets are all versioned as immutable revisions — a
`TemplateRevision` is created explicitly ("Save as new revision") and, once
referenced by a Paper, is never edited in place; Assets are content-addressed so
a replacement is a new object and identical bytes deduplicate. This replaces the
current live-reference behavior (question join + `template_version` int) that
lets editing a library item silently mutate already-assembled papers and makes
old exports unreproducible.

## Considered Options

- **Live reference** (current state). Rejected: violates "question content is
  not silently changed" and breaks reproducibility when a shared question or
  template is edited.
- **Copy-per-paper without dedup**. Rejected as a primary mechanism; content
  hashing gives the same reproducibility with shared storage.

## Consequences

- Old papers and exports remain reproducible after their sources change.
- Storage cost is bounded by content-hash dedup; only genuinely new bytes are
  stored.
- Applying source updates to a snapshot ("re-pull") is an explicit, manual
  action and never automatic. Tier 1 blocks re-pull when the snapshot has local
  edits; three-way diff/merge is deferred to Tier 2.

## Sequencing

Tier 1 (first implementation): leaf marks, Paper snapshots, no-silent-loss
import, declared-marks evidence and basic validation. Tier 2 (production
hardening): content-hash asset revisions, immutable `TemplateRevision`,
source-update/re-pull with three-way merge, final-export blocking, and a full
audit/resolution workflow.