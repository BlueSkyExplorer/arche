import { describe, it, expect } from "vitest";
import { hasSubQuestions, leafMarksTotal, type QuestionContent } from "./content";

const standalone: QuestionContent = { type: "doc", marks: 4, content: [{ type: "paragraph" }] };
const multi: QuestionContent = {
  type: "doc",
  content: [
    { type: "subQuestion", attrs: { label: "(a)", marks: 2 }, content: [{ type: "paragraph" }] },
    { type: "subQuestion", attrs: { label: "(b)", marks: 3 }, content: [{ type: "paragraph" }] },
  ],
};
const nested: QuestionContent = {
  type: "doc",
  content: [
    {
      type: "subQuestion",
      attrs: { label: "(a)" },
      content: [
        { type: "subQuestion", attrs: { label: "(i)", marks: 1 }, content: [{ type: "paragraph" }] },
        { type: "subQuestion", attrs: { label: "(ii)", marks: 2 }, content: [{ type: "paragraph" }] },
      ],
    },
  ],
};

describe("hasSubQuestions", () => {
  it("false for standalone", () => expect(hasSubQuestions(standalone)).toBe(false));
  it("true once a sub-question exists", () => expect(hasSubQuestions(multi)).toBe(true));
});

describe("leafMarksTotal", () => {
  it("returns the doc mark for a standalone question", () => expect(leafMarksTotal(standalone)).toBe(4));
  it("sums sub-part leaves", () => expect(leafMarksTotal(multi)).toBe(5));
  it("aggregates nested leaves only", () => expect(leafMarksTotal(nested)).toBe(3));
  it("returns 0 when no marks present", () => expect(leafMarksTotal({ type: "doc", content: [] })).toBe(0));
  it("preserves a zero-valued leaf mark", () =>
    expect(
      leafMarksTotal({
        type: "doc",
        content: [
          { type: "subQuestion", attrs: { label: "(a)", marks: 0 }, content: [{ type: "paragraph" }] },
        ],
      }),
    ).toBe(0));
});