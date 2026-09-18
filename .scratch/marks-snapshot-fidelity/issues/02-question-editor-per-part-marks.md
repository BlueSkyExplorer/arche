# 02: Question editor authors per-part marks

**What to build:** A teacher can set a mark on a standalone question and on each of its sub-parts in the question editor. The backend stores leaf marks and returns the computed subtotal, and the values survive save and reload unchanged.

**Blocked by:** 01.

**Status:** ready-for-agent

- [ ] The editor lets the teacher enter a mark on a standalone question.
- [ ] The editor lets the teacher enter a mark on each sub-part.
- [ ] Leaf marks round-trip through save and reload without loss or reordering.
- [ ] The question's returned subtotal equals the sum of its leaf marks.
- [ ] A sub-part that has children *and* a mark is rejected or surfaced in the editor, consistent with the schema.