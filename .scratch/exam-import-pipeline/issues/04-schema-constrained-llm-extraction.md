# 04: Schema-constrained LLM extraction + provider abstraction

**What to build:** An `LLMProvider` interface and a schema-constrained extractor
that emits the Exam IR via structured output (JSON Schema), never free-text
JSON. Replace the current `AIClient.complete_json` (`json_object` mode).

**Blocked by:** 01.

**Status:** ready-for-agent

- [ ] `LLMProvider` protocol with at least one OpenAI-compatible and one
      pluggable implementation; no vendor type leaks into `app/exam/`.
- [ ] Structured output: the provider is asked for a schema that validates into
      `ExamDocument` (e.g. `response_format={"type":"json_schema", ...}`), and
      the response is validated through `ExamDocument.model_validate`.
- [ ] Extraction prompt emits: sections, arbitrarily-deep `QuestionNode`s, leaf
      marks, declared marks, `ContentBlock`s, `SourceEvidence` (page/bbox/text),
      per-node confidence.
- [ ] AI failures / invalid schemas fall back to `RuleBasedExtractor` and flag
      `needs_review`; never a raw JSON write into the Question model.
- [ ] Tests: a mock provider returning valid + invalid + non-conforming IR; the
      extractor coerces/validates and degrades safely.
