# 03: Rule-based semantic extractor (refactor question_ingest.py → IR)

**What to build:** Re-express the deterministic splitter (including the
answer-sheet fused-label parser) as a `SemanticExtractor` implementation that
consumes `DocumentBlock[]` and emits `ExamDocument`, instead of writing
`QuestionIngestDraft` directly.

**Blocked by:** 02.

**Status:** done

## Implementation record

- `app/exam/extraction/interface.py` — `ExamExtractor` protocol
  (`extract(ParseResult) -> ExamDocument`), shared with ticket 04.
- `app/exam/extraction/numbering.py` — `detect_numbering` → `NumberingCandidate`
  (system/value/token/affix/span); `NumberingPattern` (ADR-0001) recorded to
  `meta["numbering_patterns"]`.
- `app/exam/extraction/marks.py` — `detect_marks` (value + raw + span), covering
  `(3 marks)` / `[3 marks]` / `3 marks` / `3 mark` / `(3分)`. Detection only.
- `app/exam/extraction/extractor.py` — `RuleBasedExamExtractor`: hierarchy
  reconciliation (canonical rank stack, arbitrary depth), content accumulation
  (block identity preserved), marks attachment (leaf `own_marks` vs non-leaf
  `declared_marks`), ambiguity warnings + confidence lowering.
- `tests/test_rule_based_extractor.py` — 25 tests (detection, hierarchy, marks,
  ambiguity, content preservation, source evidence, integration Q3 nested).
- `docs/adr/0006-rule-based-semantic-extraction.md` — interface, separation,
  ambiguity policy, fallback role, migration path.

**Migration path** (documented in ADR-0006): `question_ingest.py` is NOT switched
yet; steps are (1) port mark detection to `extraction.marks.detect_marks`,
(2) adapter → extractor → validate → materializer, (3) materializer (ticket 05)
writes the IR into `content_json`, retiring the old splitter.

- [x] `ExamExtractor` protocol: `extract(ParseResult) -> ExamDocument`.
- [x] `RuleBasedExamExtractor` maps `DocumentBlock[]` onto the IR.
- [ ] Answer-sheet fused labels (`1ai`/`2a`/`1M`) + MCQ grids — deferred (kept in
      `question_ingest.py` until the migration in ticket 05).
- [x] Observed `NumberingPattern` recorded to `ExamDocument.meta`.
- [x] Tests: nested `3 -> b -> ii -> 1`, marks, ambiguity, integration.
