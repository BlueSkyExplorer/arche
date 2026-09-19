# 09: `.doc` lossy-import provenance

**What to build / decide:** When a legacy `.doc` is converted to `.docx` and content is actually lost (e.g. a sub-part answer line dropped during conversion), record exactly what was lost and retain the original file so the teacher can recover it. Today the import flags `.doc` as `lossy` → `needs_review`, but it does not record *which* content was dropped nor keep the original source alongside the review draft.

**Status:** needs-triage

**Follow-up on:** 04 (import evidence / needs_review).

## Open questions

- Provenance granularity: do we store a per-region loss report (which block / text fragment failed to survive conversion), or a coarse "converted from `.doc`, may be lossy" note? The known concrete case is Q1(a) answer text being dropped by LibreOffice's `.doc`→`.docx` conversion.
- Original-file retention: keep the uploaded `.doc` attached to the ingest draft (or the resulting question) until the teacher approves, then optionally archive?
- Detect-vs-declare: can loss be detected automatically (compare source `.doc` text to converted `.docx`), or only flagged as "assume lossy"? A text-extraction diff would raise confidence but is a non-trivial, possibly OCR-free heuristic.
- Does this belong under the asset-immutability model (ADR-0003) — i.e. the original `.doc` becomes a retained asset revision?