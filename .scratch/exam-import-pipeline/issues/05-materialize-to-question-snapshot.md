# 05: Materialization → Question / Paper snapshot

**What to build:** A deterministic converter from a validated `ExamDocument` to
Arche's canonical content, persisting referenced assets and producing Paper
snapshots.

**Blocked by:** 01, 03.

**Status:** ready-for-agent

- [ ] `materialize(doc, report) -> list[QuestionIngestDraft]` maps
      `QuestionNode` (arbitrary depth) onto `SubQuestionNode` (already
      recursive), leaf `marks` onto `attrs.marks`, and `declared_marks` into
      evidence.
- [ ] Referenced `AssetReference.local_id` values are persisted as `Asset`
      records and rewritten to `asset_id` (ADR-0003 content-addressed).
- [ ] `needs_review` / `validation_issues` from `ValidationReport` flow into
      `QuestionIngestDraft`.
- [ ] Paper assembly still snapshots content (`content_snapshot_json`); source
      question edits never mutate an assembled paper (ADR-0003).
- [ ] No DB migration required unless provenance/confidence is persisted; if
      persisted, add an additive migration + `source_note`-style evidence.
- [ ] Tests: round-trip `ExamDocument -> QuestionIngestDraft -> content_json ->
      computed_marks` preserves totals; snapshot immutability retained.
