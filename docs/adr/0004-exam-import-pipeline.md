---
status: accepted
date: 2026-09-20
---

# Exam import pipeline: layered, IR-centric extraction

The deterministic splitter in `question_ingest.py` is tuned to a handful of
question-paper layouts and cannot generalize across schools, years, subjects,
page breaks, images, tables, or formulas. The current AI path
(`ai_client.py` / `ai_schema.py`) is a minimal OpenAI-`json_object` call whose
output is already a fixed two-level shape — it is neither schema-constrained,
provider-independent, nor layout-aware, and it writes straight into the
canonical content tree, mixing semantic structure with the source's formatting.

We introduce a pipeline whose spine is a **provider-independent Exam IR**, with
the semantic question structure and the source layout/formatting kept as
separate, traceable layers, and all computation delegated to deterministic code.

## Considered Options

### Option 1 — Layered, IR-centric pipeline (chosen)

```
PDF / DOCX / Image
  → document parsing / OCR / layout extraction   →  DocumentBlock[]
  → semantic structure extraction (rule-based or LLM) →  Exam IR (ExamDocument)
  → deterministic validation / reconciliation    →  ValidationReport
  → materialization                              →  QuestionIngestDraft → content_json
```

- **Semantic vs layout are separate.** `QuestionNode`/`ContentBlock` hold
  meaning; `LayoutReference`/`SourceEvidence` hold font/bbox/page/source text.
- **Provider-independent IR** (`ExamDocument`, `Section`, `QuestionNode`,
  `ContentBlock`, `AssetReference`, `SourceEvidence`, `LayoutReference`,
  `ExtractionConfidence`, `ValidationIssue`). Providers *adapt into* it; nothing
  in the IR imports a vendor.
- **Schema-constrained output.** LLM extractors must emit into the IR via a
  JSON Schema / structured-output contract, never free-text JSON.
- **Deterministic validation** (numbering, marks totals, tree consistency,
  orphans, page ranges, asset references, declared-vs-computed) lives in one
  module, independent of any AI.

Trade-offs: more code and a new subsystem up front; the existing splitter must
be re-expressed as one extractor implementation. In exchange, every layer is
independently testable, providers are swappable, and unknown formats degrade to
`needs_review` instead of a silent wrong parse.

### Option 2 — Incremental extension of `question_ingest.py`

Keep the current splitter and bolt on a `DocumentBlock` normalizer, a richer AI
IR, and inline validation.

Trade-offs: smaller diff, faster to start, backward compatible. Rejected: the
semantic/layout split and provider independence become bolted-on (the exact
"shortcut" this work exists to remove); the IR stays entangled with the OpenAI
client; validation is not a standalone, testable layer.

## Decision

Option 1. The requirements (provider-independent IR, schema-constrained
structured output, semantic/layout separation, deterministic reconciliation)
are first-class in this shape and only retrofits in Option 2. The existing
deterministic splitter is preserved as the *default rule-based extractor*, so
backward compatibility is maintained through the same IR boundary.

## Marks semantics (Phase 1.1)

The Exam IR distinguishes *authoritative* from *derived* mark quantities so that
a partial result is never mistaken for a complete total:

- `own_marks` — authoritative mark; legal on a leaf node only.
- `known_marks_total` — sum of all *known* descendant leaf marks (unknown leaves
  add nothing).
- `marks_complete` — true only when every descendant leaf has a known mark.
- `computed_marks` — the leaf sum when `marks_complete` is true; **`None` when
  any leaf mark is unknown**. It is never silently the known subtotal.

`needs_review` is retained but is *not* a proxy for `marks_complete` — it is also
set by low confidence, numbering conflicts, page gaps, and asset issues.

Example: `Q3 -> (a)=2, (b)=unknown` yields `known_marks_total=2`,
`marks_complete=False`, `computed_marks=None`.

## Consequences

- New `app/exam/` subsystem: `ir.py` (contract), `validation.py` (deterministic
  checks), `parsing/` (document parsing layer, ADR-0005). Later phases add
  `extraction/` and `providers/`.
- The Exam IR re-affirms ADR-0002 (leaf-only marks; declared = evidence) and
  ADR-0003 (snapshot immutability; the materializer writes the snapshot from the
  IR, never a live source).
- **No migration yet.** The IR and validation are non-persisted; materialization
  (a later phase) maps the IR onto the existing `content_json` shape, which is
  backward compatible. A DB migration is required only if provenance (source
  evidence/confidence) is later persisted alongside a `Question`.
- AI remains reviewable and non-required: rule-based extraction always runs, and
  LLM extraction is an opt-in provider behind the same IR.
