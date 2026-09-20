---
status: accepted
date: 2026-09-20
---

# Semantic extraction baseline: deterministic rule-based extractor

Ticket 03 of the exam-import pipeline. A deterministic extractor that turns
`ParseResult` / `DocumentBlock[]` into an `ExamDocument` (the Exam IR), as the
baseline and fallback that the LLM extractor (ticket 04) shares a contract with.

## Extractor interface

```python
class ExamExtractor(Protocol):
    name: str
    def extract(self, parsed: ParseResult) -> ExamDocument: ...
```

`RuleBasedExamExtractor` implements it now; `LLMExamExtractor` (ticket 04) will
implement the same contract. Downstream — deterministic validation
(`validate_exam_document`) and materialization — consume `ExamDocument` only,
so swapping the extractor never changes them.

## Responsibilities are separated (not one big regex)

1. **Numbering candidate detection** (`numbering.py::detect_numbering`) — given a
   text block, returns a `NumberingCandidate` (system, value, token, affix,
   span). It only answers "this looks like a label"; it never decides
   parent/child.
2. **Mark candidate detection** (`marks.py::detect_marks`) — returns value +
   raw text + span for `(3 marks)` / `[3 marks]` / `3 marks` / `3 mark` /
   `(3分)`. Detection only; no attachment.
3. **Hierarchy reconciliation** (`extractor.py`) — builds the `QuestionNode`
   tree from the candidate sequence + a canonical depth ranking, closing deeper
   nodes on a shallower candidate ("return to higher level"). Arbitrary depth;
   no fixed Question/SubQuestion/SubSubQuestion levels.
4. **Content accumulation** — blocks between labels become `ContentBlock`s,
   preserving block identity (image/table/equation/caption), order, and source
   evidence.
5. **Marks attachment** — post-pass over the finished tree: leaf -> `own_marks`;
   non-leaf total -> `declared_marks` (subtotal evidence only). Unknown stays
   `None`, never 0.

## Canonical depth ranking

`arabic-dot`(0) → `alpha`(1) → `roman`(2) → `arabic-paren`(3) is the canonical
nesting, chosen so `3 → (b) → (ii) → (1)` yields four levels. It is a *default*
refined by observation (observed patterns are recorded in `meta`), not a
per-school special case. A paper that deviates (e.g. `(1)` directly under `1.`)
is surfaced as a `numbering_level_jump` warning.

## Ambiguity policy (safe failure)

The extractor never fabricates a parent, a mark, or a level. On ambiguity it
preserves what it can, lowers the node's `confidence` below the validation
threshold (so `validate_exam_document` flags `needs_review`), and records an
`extraction_warning` in `meta`. Cases: orphan numbering, level jumps,
non-monotonic/duplicate labels, multiple mark candidates on one leaf, content
before any question, and mark tokens before any question.

## Fallback role

`RuleBasedExamExtractor` is the deterministic baseline and the fallback when the
LLM extractor is disabled, errors, or returns low confidence. Rule-based
extraction always runs and remains independently testable.

## Migration path (backward compatibility)

The existing `question_ingest.py` splitter (and its `_MARKS_EN` / `_QUEST_START`
regexes) is **not** switched to this boundary yet — the production ingest path is
unchanged. Migration steps:

1. Port `question_ingest.py` mark detection to `extraction.marks.detect_marks`
   (a superset of `_MARKS_EN` / `_MARKS_ZH`), deleting the duplicated regexes.
2. Add a `DocumentBlock[]`-producing adapter over the DOCX parse, then route
   `RuleBasedExamExtractor` → `validate_exam_document` → materializer.
3. Materializer (ticket 05) writes the `ExamDocument` into the existing
   `QuestionIngestDraft` / `content_json` shape, at which point the old splitter
   becomes a thin alias for the new boundary.

## Consequences

- New `app/exam/extraction/`: `interface.py`, `numbering.py`, `marks.py`,
  `extractor.py`.
- No LLM, no OCR, no DB, no provider-specific logic; CJK numeral systems remain
  reserved (ADR-0001) and are not rendered.
- The LLM extractor (ticket 04) emits the same `ExamDocument` and reuses
  `validate_exam_document`, so its output is validated by the exact same
  deterministic rules.
