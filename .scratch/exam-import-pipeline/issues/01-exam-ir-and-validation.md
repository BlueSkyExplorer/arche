# 01: Exam IR + deterministic validation

**What to build:** The provider-independent Exam IR and the deterministic
validation/reconciliation engine.

**Blocked by:** None.

**Status:** done

- [x] `app/exam/ir.py` defines `ExamDocument`, `Section`, `QuestionNode`,
      `ContentBlock`, `AssetReference`, `SourceEvidence`, `LayoutReference`,
      `ExtractionConfidence`, `ValidationIssue` (ADR-0004).
- [x] `QuestionNode.children` is recursive — arbitrary depth (`3 -> b -> ii`).
- [x] Leaf-only authoritative marks; a non-leaf node with `marks` is rejected.
- [x] `app/exam/validation.py` runs deterministic reconciliation: leaf marks,
      declared-vs-computed (total + subtotal + node), unknown marks (null, never
      0), missing numbering, orphan nodes, page gaps/order, asset reference
      integrity, confidence aggregation → `ValidationReport`.
- [x] Tests cover normal, nested multipart, cross-page, unknown marks,
      conflicting subtotal, missing numbering, orphan, image/table/equation,
      low-confidence, dangling/unreferenced assets (24 tests).
