---
status: accepted
date: 2026-09-18
---

# Marks truth model: leaf-only authoritative marks, declared marks as evidence

Only a leaf node may carry an authoritative mark; a node with children is always
the computed sum of its descendant leaf marks and can never hold its own
`own_marks`. A childless question is its own leaf. Marks stated in source
material are stored as `declared_marks` evidence at whichever node they appear
(paper total, section subtotal, question subtotal, sub-part), never as scoring
truth. The legacy single `Question.marks` field and the paper-level
`marks_override` are abolished.

## Consequences

- `computed_total_marks` is always Σ of leaf marks; `declared_*` values only feed
  validation diagnostics.
- A declared-vs-computed mismatch becomes a **validation issue** that a human
  must resolve by explicit acknowledgement — it must not be resolved by editing
  marks to force agreement.
- An unresolved blocking issue prevents a **final** export; a **draft** export
  only annotates it.
- This is a schema change (sub-parts must carry marks the current
  `SubQuestionNode` does not) and requires an additive migration to move existing
  `Question.marks` / `marks_override` data into the leaf representation.