# 03: Paper snapshot on add

**What to build:** Adding a question to a paper freezes its content at that moment into an independent snapshot, with a record of which source question it came from. Editing or deleting the library question afterwards does not change the assembled paper.

**Blocked by:** 01.

**Status:** ready-for-agent

- [ ] Adding a question to a section materializes an independent copy of its content.
- [ ] The paper records which source question each snapshot came from (provenance).
- [ ] Editing the source question afterwards does not change the assembled paper's content or marks.
- [ ] Deleting or archiving the source question does not break or alter the assembled paper.
- [ ] Reordering operates on the paper's snapshots and never mutates the source questions.