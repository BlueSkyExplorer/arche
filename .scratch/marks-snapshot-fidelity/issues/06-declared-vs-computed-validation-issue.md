# 06: Declared-vs-computed validation issue

**What to build:** When a declared value disagrees with the computed value, the system raises a basic validation issue and shows it to the teacher as `needs_review`, without silently changing either value to force agreement.

**Blocked by:** 04, 05.

**Status:** ready-for-agent

- [ ] A mismatch between `declared_marks` and computed marks produces a validation issue.
- [ ] Neither the declared value nor the computed value is silently edited to make them match.
- [ ] The issue is surfaced to the teacher for review in the basic Tier 1 form.