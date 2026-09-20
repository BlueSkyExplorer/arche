---
status: accepted
date: 2026-09-20
---

# LLM semantic extraction: reference-based, schema-constrained

Ticket 04 of the exam-import pipeline. An LLM extractor that shares the
`ExamExtractor` contract with the rule-based extractor and emits the same
provider-independent `ExamDocument`, so downstream validation and materialization
never change.

## Selected semantic-output strategy: Option B (reference-based)

- **Option A — LLM outputs the full `ExamDocument`.** Pros: one-step. Cons: the
  LLM regenerates content text (hallucination + source drift), needs a large
  duplicated schema, and burns tokens re-emitting text the parser already has.
- **Option B (chosen) — LLM outputs semantic *references*.** The LLM emits only
  structure: nodes with `parent_id`, `label`, ordered `content_block_ids`, section
  groupings, and per-node `confidence`. A deterministic assembler maps those
  references back onto the original `DocumentBlock[]`, reusing the rule-based
  extractor's content/mark/evidence helpers.

Option B makes content fabrication *structurally impossible*: the DTO has no text
or mark-value field, so the LLM cannot invent content, marks, labels-as-content,
or block ids that matter. It also keeps one Exam IR (no parallel AI schema) and
drops token cost.

## Schema-constrained output (hard requirement)

No `response_format=json_object` + free text. The DTO is a flat Pydantic model
(parent ids, not recursive children — recursion is disallowed by OpenAI strict
mode), and `strict_json_schema()` derives a strict-compatible JSON Schema
(inlines `$defs`/`$ref`, collapses `anyOf [T, null]` → `type: [T, "null"]`,
`additionalProperties: false`, all fields `required`). The provider adapter sends
it as `response_format={"type": "json_schema", ..., "strict": true}`. The DTO is
the single source of truth for both the provider schema and response decoding.

## Provider abstraction

`StructuredLLMClient` protocol (`complete_structured(schema, messages) -> dict`)
is the only seam. Production adapter: `AIClient.complete_structured`
(OpenAI-compatible, reusing the existing `ai_client.py` config). Test adapter:
`FakeStructuredClient`. Anthropic/Gemini/local models later implement the same
protocol. The legacy `AIClient.complete_json` (`json_object`) is retained only
for `question_ingest.py` and retires with the production switch.

## Evidence-first + hallucination safeguards

- The LLM references blocks only by `block_id`; the assembler validates every
  `block_id ∈` input ids. Unknown ids → warning + lowered node confidence, never
  silently dropped or fabricated.
- Duplicate block assignment → warning.
- Marks are never LLM-valued: the assembler runs `detect_marks` on the referenced
  blocks, so a mark is always evidenced by source text. No source mark → no
  authoritative `own_marks`.
- Content is always the verbatim source block, never generated.

## Confidence semantics

`SemanticNodeDTO.confidence` is the AI's certainty about *semantic interpretation*
(label, parent, grouping), bounded 0..1. It is distinct from parser/OCR confidence
(lives on `SourceEvidence`/`DocumentBlock`). The assembler copies it to
`QuestionNode.confidence`; ambiguity lowers it below the validator's threshold so
`validate_exam_document` flags `needs_review`. No other confidence machinery.

## Fallback policy

`LLMExamExtractor` falls back to `RuleBasedExamExtractor` on any
`StructuredLLMError` or DTO `ValidationError`, recording `fallback_occurred` in
`meta`. The rule-based extractor remains the deterministic baseline, regression
reference, and provider-failure fallback (no ensemble in this phase).

## Chunking boundary

Single-pass now: the whole `DocumentBlock[]` is sent in one request. The domain
contract carries no single-call assumption — `ExamExtractor.extract(ParseResult)`
already takes a normalized block list, so a future large-document path can chunk
blocks (page/section windows), extract per chunk, and reconcile `ExamDocument`s
without changing the interface.

## Security / prompt injection

Document text is untrusted input. `build_messages` keeps all blocks in the *user*
message as data, separated from the system prompt, which states explicitly that
blocks are untrusted content that must never change the extraction rules. The
schema/DTO gives the model no channel to emit instructions back.

## Consequences

- New `app/exam/extraction/`: `providers.py`, `semantic.py` (DTO + strict schema +
  prompt repr), `assembler.py`, `llm_extractor.py`; `content.py` extracted shared
  deterministic helpers (also used by the rule-based extractor).
- `ai_client.py` gains `complete_structured` (schema-constrained) alongside the
  legacy `complete_json`.
- Ticket 05 consumes the same `ExamDocument` from either extractor; it has no
  knowledge of which extractor produced it.
