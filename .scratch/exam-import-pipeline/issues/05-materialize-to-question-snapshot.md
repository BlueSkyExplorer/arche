# 05: Materialization → Question / Paper snapshot

**What to build:** A deterministic converter from a validated `ExamDocument` to
Arche's canonical content, persisting referenced assets and producing Paper
snapshots.

**Blocked by:** 01, 03.

**Status:** done (materializer + field mapping; asset persistence + production wiring deferred)

## Implementation record

- `app/exam/materialization/materializer.py` — `materialize_exam_document(document,
  *, asset_id_for=None) -> list[QuestionIngestDraft]`, a pure function.
  - Maps `QuestionNode` (arbitrary depth) onto nested `SubQuestionNode`.
  - Leaf `own_marks` → `attrs.marks`/`DocNode.marks`/draft `marks`; unknown → `None`
    (never 0); non-leaf → `None` (total computed from leaves).
  - `declared_marks` → draft `declared_marks` (subtotal evidence).
  - Image blocks resolved via injectable `asset_id_for(local_id) -> UUID`;
    unresolved images are flagged (`unresolved_image_asset` + `needs_review`).
  - `needs_review` / `validation_issues` flow from `validate_exam_document`.
- `tests/test_materializer.py` — 11 tests (marks invariant, arbitrary depth,
  declared subtotal, image with/without resolver, table, equation/heading lossy
  mapping, section flattening, end-to-end extractor→materializer).
- `docs/adr/0008-exam-ir-materialization.md` — field mapping table + A/B/C gap
  classification.

**Deferred (not in this ticket):** asset byte persistence (the caller provides
`asset_id_for`); production ingest wiring (no forced switch — ticket 18); Paper
snapshot assembly; provenance/confidence persistence (needs an additive
migration, classified C).

- [x] `materialize_exam_document` maps arbitrary-depth `QuestionNode` → nested
      `SubQuestionNode`, leaf `marks` → `attrs.marks`, `declared_marks` → evidence.
- [x] `AssetReference.local_id` → `asset_id` via injectable resolver (persistence
      itself deferred to the caller — no silent drop, flagged `needs_review`).
- [x] `needs_review` / `validation_issues` flow from `ValidationReport`.
- [ ] Paper snapshot assembly — not part of this ticket (existing snapshot path
      unchanged; ADR-0003 still holds).
- [x] No DB migration required (provenance/confidence are classified C, deferred).
- [x] Tests: `ExamDocument → QuestionIngestDraft → content_json` preserves totals
      (leaf marks, unknown→None, non-leaf computed).
