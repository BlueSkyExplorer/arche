Status: in-progress

# Exam import pipeline (generalizable question extraction)

A layered, provider-independent pipeline that turns any school paper
(PDF / DOCX / image) into Arche's canonical question content, with the semantic
structure and source layout kept separate and everything traceable back to
source evidence (page / bbox / source text / confidence). Governed by ADR-0004.

## Layers

1. **Parsing / layout** — a document format into normalized `DocumentBlock[]`
   (text/image/table/equation/answer-space) with page + bbox.
2. **Semantic extraction** — `DocumentBlock[]` into the Exam IR
   (`ExamDocument`), via a rule-based extractor (default, no AI) and/or a
   schema-constrained LLM provider.
3. **Validation / reconciliation** — deterministic; produces `ValidationReport`
   (issues + `needs_review` + computed totals). Already implemented.
4. **Materialization** — Exam IR into `QuestionIngestDraft` → `content_json`,
   persisting referenced assets and writing Paper snapshots (ADR-0003).

## Invariants

- Only leaf nodes carry authoritative `marks`; parents are computed sums
  (ADR-0002). Declared values are evidence only.
- Unknown marks stay `null` + `needs_review`, never `0`.
- AI output must be schema-constrained structured output, not free-text JSON.
- Providers are swappable; no vendor type leaks into the IR or the domain model.
- Existing `question_ingest.py` behavior is preserved as the rule-based
  extractor; the Answer-Sheet parser is folded into that same layer.

## Status

- `01` Exam IR + deterministic validation — **done** (`app/exam/ir.py`,
  `app/exam/validation.py`, 24 tests).
- `02` Document parsing layer — pending.
- `03` Rule-based extractor (refactor `question_ingest.py` → IR) — pending.
- `04` Schema-constrained LLM extraction (provider interface) — pending.
- `05` Materialization → Question/Paper snapshot — pending.
- `06` Review UI (source evidence / confidence) — pending.
