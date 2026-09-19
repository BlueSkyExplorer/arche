# 05: Paper computed marks + snapshot-based rendering

**What to build:** The paper's computed total is the sum of all leaf authoritative marks. Preview and export read the paper snapshot — never dereferencing the live Question for content or marks — and render leaf marks at the template's mark position. A parent declared subtotal may be displayed but never participates in computed scoring. Preview and export agree.

**Blocked by:** 03.

**Status:** done

- [x] The paper's computed total equals the sum of all leaf authoritative marks.
- [x] Preview and export read the snapshot for content and marks, never the live Question.
- [x] Leaf marks render at the template's mark position (right / inline / below).
- [x] A parent or section subtotal shown is the sum of its descendants and never double counts its own value.
- [x] A declared subtotal, if displayed, is shown as evidence and never feeds the computed scoring.
- [x] Preview and export produce identical totals.
- [x] Reordering questions keeps the computed total correct.