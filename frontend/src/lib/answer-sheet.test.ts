import { describe, expect, it } from "vitest";
import { leafMarks, totalsMismatch } from "./answer-sheet";
import type { AnsNode, AnsSection } from "@/lib/api/exam-imports";

describe("leafMarks", () => {
  it("sums leaf marks through a multipart hierarchy", () => {
    const q1: AnsNode = {
      label: "Q1",
      children: [
        { label: "(a)", answer: ["二氧化碳", "尿素"], marks: "2" }, // multiline answer, 2 marks
        {
          label: "(b)",
          children: [
            { label: "(i)", marks: "1" },
            { label: "(ii)", marks: 1 }, // numeric marks accepted
          ],
        },
      ],
    };
    expect(leafMarks(q1)).toBe(4);
  });

  it("treats a standalone question as a leaf", () => {
    expect(leafMarks({ label: "Q2", marks: "5" })).toBe(5);
  });

  it("returns null (not 0) when any descendant mark is unknown", () => {
    const node: AnsNode = {
      label: "Q3",
      children: [{ label: "(a)", marks: "2" }, { label: "(b)", marks: null }],
    };
    expect(leafMarks(node)).toBeNull();
  });

  it("returns null for a non-leaf with all-unknown marks", () => {
    const node: AnsNode = {
      label: "Q4",
      children: [{ label: "(a)", marks: null }, { label: "(b)", marks: "" }],
    };
    expect(leafMarks(node)).toBeNull();
  });
});

describe("totalsMismatch", () => {
  it("flags a declared/computed mismatch (50 vs 53)", () => {
    const section: AnsSection = {
      title: "乙部",
      declared_total: "50",
      computed_total: "53",
      questions: [],
    };
    expect(totalsMismatch(section)).toBe(true);
  });

  it("does not flag when totals agree", () => {
    const section: AnsSection = {
      title: "乙部",
      declared_total: "50",
      computed_total: "50",
      questions: [],
    };
    expect(totalsMismatch(section)).toBe(false);
  });

  it("does not flag when either total is absent", () => {
    expect(totalsMismatch({ title: "甲部", declared_total: "30", questions: [] })).toBe(false);
    expect(totalsMismatch({ title: "乙部", computed_total: "4", questions: [] })).toBe(false);
  });
});
