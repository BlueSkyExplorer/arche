# 03: Rule-based semantic extractor (refactor question_ingest.py → IR)

**What to build:** Re-express the deterministic splitter (including the
answer-sheet fused-label parser) as a `SemanticExtractor` implementation that
consumes `DocumentBlock[]` and emits `ExamDocument`, instead of writing
`QuestionIngestDraft` directly.

**Blocked by:** 02.

**Status:** ready-for-agent

- [ ] A `SemanticExtractor` protocol: `extract(blocks) -> ExamDocument`.
- [ ] `RuleBasedExtractor` moves `question_ingest.py` logic onto the IR; the
      existing `POST /questions/ingest` output is unchanged (backward compat
      via the materializer in 05).
- [ ] Answer-sheet fused labels (`1ai`/`2a`/`1M`) and MCQ grids map into
      `QuestionNode` trees; every node carries `SourceEvidence` (page/block).
- [ ] Numbering detection records the observed `NumberingPattern` (ADR-0001)
      into `ExamDocument.meta` rather than hard-coding levels.
- [ ] Tests: the existing `test_question_ingest.py` fixtures still produce the
      same structures through the IR; nested `3 -> b -> ii` preserved.
