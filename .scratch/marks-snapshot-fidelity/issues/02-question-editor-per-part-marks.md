# 02: Question editor authors per-part marks

**What to build:** A teacher can set a mark on a standalone question and on each of its sub-parts in the question editor. The backend stores leaf marks and returns the computed subtotal, and the values survive save and reload unchanged.

**Blocked by:** 01.

**Status:** done

- [x] The editor lets the teacher enter a mark on a standalone question.
- [x] The editor lets the teacher enter a mark on each sub-part.
- [x] Leaf marks round-trip through save and reload without loss or reordering.
- [x] The question's returned subtotal equals the sum of its leaf marks.
- [x] A sub-part that has children *and* a mark is rejected or surfaced in the editor, consistent with the schema.