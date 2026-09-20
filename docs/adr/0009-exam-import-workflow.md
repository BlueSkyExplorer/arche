---
status: accepted
date: 2026-09-20
---

# Exam-import workflow: durable upload → extract → review → approve

A user-operable vertical slice that turns the Exam pipeline (parse → extract →
validate → materialize) into a product flow with a durable entity, a review UI,
and Question Library persistence.

## Workflow

```
Upload (.docx/.pdf/.doc)
  → parse_document() → DocumentBlock[]
  → extractor (LLM if enabled, else rule-based; LLM falls back to rule-based)
  → validate_exam_document() → ValidationReport
  → persist ExamImport (blocks + extracted/reviewed documents + validation)
  → Review UI (view + edit reviewed document)
  → Approve (validate → materialize → persist Questions → completed)
```

## ExamImport entity

JSON-column-heavy, additive table (`exam_imports`, migration 0005). Stores the
source reference, parsed `blocks_json`, `extracted_document_json` and
`reviewed_document_json` (kept separate — human edits never overwrite the
original extraction), `validation_json`, extractor/provider/model/schema
metadata, and `asset_manifest` (local_id → storage key) so image bytes survive
to approve-time Asset persistence.

## State machine

`uploaded → parsing → extracting → needs_review | ready | failed`; approve:
`needs_review | ready → materializing → completed | failed`. Transitions are
enforced (`can_transition`); terminal states are `completed` and `failed`.

## Extractor selection

`AIClient.enabled` (i.e. `AI_ENABLED` + a key) → `LLMExamExtractor` (which
falls back to rule-based on provider error); otherwise `RuleBasedExamExtractor`.
The import records `extractor_name` / `provider` / `model` / `fallback_occurred`
so the UI can show "Rule-based" vs "AI" and "fallback occurred" — never a silent
fallback. The product works end-to-end with AI disabled.

## Review editing

The review page edits the *reviewed* document: label, marks (empty = unknown,
never 0), add/remove/re-parent nodes. Saving re-validates and stores the
reviewed document; the original extraction is always retained.

## Validation gate

Approve re-validates the reviewed document and refuses (409) when blocking
issues remain or an image asset's source is missing (correctness-critical). A
non-leaf with `own_marks` is rejected at IR construction before it can persist.

## Consequences

- New `app/models/exam_import.py`, `app/services/exam_imports.py`,
  `app/api/v1/routes/exam_imports.py`, `app/schemas/exam_import.py`.
- Frontend: `features/imports/` (list + review), `/imports` and `/imports/[id]`
  routes, `lib/api/exam-imports.ts`.
- The legacy `question_ingest.py` path is untouched; this workflow is additive
  and coexists with it until a later cutover.
