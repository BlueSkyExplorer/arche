# 07: Contract — remove Question.marks & marks_override

**What to build:** Migrate every remaining consumer to leaf marks and drop the two legacy fields, leaving a single source of scoring truth.

**Blocked by:** 02, 06.

**Status:** ready-for-agent

- [ ] No consumer reads the legacy single question-level `marks` or the paper-level `marks_override`.
- [ ] The two legacy fields are removed via an additive migration.
- [ ] Numbering, export, and the renderer read only leaf marks.
- [ ] Existing questions and papers keep working through and after the migration.