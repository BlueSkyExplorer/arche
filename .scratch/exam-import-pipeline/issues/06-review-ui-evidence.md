# 06: Review UI — source evidence + confidence

**What to build:** Surface extraction provenance (page / bbox / source text /
confidence) and validation issues in the existing ingest review UI so a teacher
can trace any value back to the source.

**Blocked by:** 01, 03, 05.

**Status:** ready-for-agent

- [ ] Ingest review panel shows per-question confidence and `needs_review`
      reasons (unknown marks, mismatch, missing numbering, page gap).
- [ ] Each question/sub-part shows a link/highlight to its source page/text so
      values are verifiable.
- [ ] Validation issues are listed with severity and an explicit resolution
      affordance (acknowledge), consistent with ADR-0002.
- [ ] Images/tables/equations render as reviewable placeholders with their
      source location before save.
