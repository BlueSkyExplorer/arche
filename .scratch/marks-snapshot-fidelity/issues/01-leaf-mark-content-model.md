# 01: Leaf-mark content model & aggregation

**What to build:** The canonical content representation lets a teacher's question carry marks where they actually belong — on a standalone question and on its nested sub-parts — while a node that has children *and* an authoritative mark is rejected. Ancestor totals are computed as the sum of descendant leaf marks. Existing question-level marks behavior is untouched in this ticket (expand phase).

**Blocked by:** None (can start immediately).

**Status:** done

- [x] A standalone question with no sub-parts can carry a mark on the question root (it is its own leaf).
- [x] A nested sub-question that has no children can carry a mark.
- [x] A node with children *and* an authoritative mark is rejected at validation time, not merely "not counted" during aggregation.
- [x] Ancestor totals are computed as the sum of descendant leaf marks, with no parent-held `own_marks`.
- [x] The legacy single question-level `marks` and the paper-level `marks_override` continue to behave exactly as before, so nothing breaks while the new form lands beside the old.