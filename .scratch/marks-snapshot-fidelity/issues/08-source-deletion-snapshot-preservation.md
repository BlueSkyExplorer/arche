# 08: Source-deletion snapshot preservation

**What to build / decide:** A paper's question snapshot must remain complete and reproducible even after its source question is eventually deleted or purged. Today a hard delete of a referenced question is blocked with a 409, so an assembled paper is never broken — but there is no path to purge a source question once papers reference it, and no tombstone / historical reference for when it is gone.

**Status:** needs-triage

**Follow-up on:** 03 (paper snapshot on add), 07 (contract removal).

## Open questions

- Delete semantics: hard-delete with a nullable/tombstone `source_question_id`, or archive-only (no purge)? ADR-0003 leans toward "source reference becomes a tombstone / nullable historical reference".
- The `paper_questions.question_id` FK is non-nullable today; purging a source must not cascade to or block papers. Decide whether to relax the FK or introduce a tombstone row.
- What historical reference (title, content hash, revision) should the snapshot retain once the source no longer exists, so provenance is still traceable?
- Interaction with `QuestionRevision` (Tier 2) and content-hash identity: does a purge also archive revisions, or only the current source record?