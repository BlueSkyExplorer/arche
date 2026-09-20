import type { AnsNode, AnsSection } from "@/lib/api/exam-imports";

/**
 * Sum of a node's leaf marks. Non-leaf totals are always derived from
 * descendant leaves (leaf-only-marks invariant, ADR-0004); an unknown leaf
 * mark (null/undefined/"") makes the whole subtree total null — never 0.
 */
export function leafMarks(node: AnsNode): number | null {
  if (node.children && node.children.length > 0) {
    const vals = node.children.map(leafMarks);
    if (vals.some((v) => v === null)) return null;
    return vals.reduce((a, b) => (a ?? 0) + (b ?? 0), 0);
  }
  const m = node.marks;
  return m === null || m === undefined || m === "" ? null : Number(m);
}

/** True when a section's declared total disagrees with its computed leaf total. */
export function totalsMismatch(section: AnsSection): boolean {
  const d = section.declared_total;
  const c = section.computed_total;
  return d != null && c != null && String(d) !== String(c);
}
