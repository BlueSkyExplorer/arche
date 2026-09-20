# 04: Schema-constrained LLM extraction + provider abstraction

**What to build:** An `LLMProvider` interface and a schema-constrained extractor
that emits the Exam IR via structured output (JSON Schema), never free-text
JSON. Replace the current `AIClient.complete_json` (`json_object` mode).

**Blocked by:** 01.

**Status:** done

## Implementation record

Reference-based output (Option B): the LLM emits structure only; the
deterministic assembler maps block references back onto the original
`DocumentBlock[]` and reuses the rule-based extractor's content/mark helpers.

- `app/exam/extraction/providers.py` — `StructuredLLMClient` protocol +
  `FakeStructuredClient` (test). Production adapter = `AIClient.complete_structured`.
- `app/exam/extraction/semantic.py` — flat `SemanticExtractionResult` DTO
  (nodes w/ parent_id + content_block_ids, sections), `strict_json_schema()`
  (strict-compatible), `build_input_blocks`/`build_messages` (untrusted-data
  separation).
- `app/exam/extraction/assembler.py` — deterministic `assemble()`: block-ref
  validation (unknown id / duplicate assignment), content mapping, deterministic
  mark detection/attachment, evidence.
- `app/exam/extraction/llm_extractor.py` — `LLMExamExtractor` (orchestration +
  rule-based fallback on `StructuredLLMError`/`ValidationError`).
- `app/exam/extraction/content.py` — extracted shared deterministic helpers
  (now used by both extractors).
- `app/services/ai_client.py` — added `complete_structured` (json_schema strict)
  alongside legacy `complete_json`.
- `tests/test_llm_extractor.py` — 22 tests (schema boundary, semantic extraction,
  hallucination safety, marks invariant, prompt injection, baseline comparison).
- `docs/adr/0007-llm-semantic-extraction.md`.

- [x] `StructuredLLMClient` protocol + OpenAI-compatible + fake adapters; no
      vendor type leaks into `app/exam/` (DTO is provider-independent).
- [x] Structured output via `response_format={"type":"json_schema",...,"strict":true}`;
      response validated through the Pydantic DTO, not raw JSON.
- [x] Prompt emits sections / arbitrary-depth nodes / block references / confidence.
- [x] Provider failure / schema violation → fallback to `RuleBasedExamExtractor` +
      `fallback_occurred` flag; never a raw JSON write into the Question model.
- [x] Tests: fake provider returning valid + invalid + non-conforming results;
      safe degradation.
