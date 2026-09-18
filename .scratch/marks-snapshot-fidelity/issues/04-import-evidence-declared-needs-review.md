# 04: Import evidence — declared marks, needs_review, no fabricated 0

**What to build:** Import captures the marks a source document states as *declared evidence* (distinct from authoritative leaf marks), preserves anything it cannot reliably map, flags it `needs_review`, and never writes a `0` mark it merely failed to detect. The review UI surfaces all of this before the teacher saves.

**Blocked by:** 01.

**Status:** ready-for-agent

- [ ] Stated marks are stored as `declared_marks` evidence at the level the source states them (paper, section, question, sub-part).
- [ ] A non-leaf node may carry `declared_marks` (e.g. `4` stated above `(a)=2, (b)=2`) but never an authoritative mark — evidence and truth are kept distinct.
- [ ] A mark the parser failed to detect is left absent, never set to `0`.
- [ ] Content the parser cannot reliably map is preserved (raw fragment/reference) and flagged `needs_review`, never dropped.
- [ ] A lossy `.doc` conversion is flagged `needs_review` rather than reported as a clean import.
- [ ] The ingest review UI displays declared evidence and `needs_review` flags before the teacher commits anything.