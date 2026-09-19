import { describe, it, expect } from "vitest";
import {
  resolveEffective,
  buildDraftPayload,
  sharedDefaultsSchema,
  draftOverrideSchema,
} from "@/lib/validation/ingest-batch";
import type { QuestionIngestDraft } from "@/lib/api/questions";
import type { QuestionContent } from "@/lib/validation/content";

// Minimal fixture
const stubContent: QuestionContent = {
  type: "doc",
  content: [{ type: "paragraph", content: [{ type: "text", text: "2+2=?" }] }],
};

const stubDraft: QuestionIngestDraft = {
  internal_title: "Q1",
  subject: "",
  level: "",
  tags_json: ["algebra"],
  source_note: null,
  content_json: stubContent,
  marks: 2,
  declared_marks: [],
  needs_review: false,
  validation_issues: [],
  status: "draft",
};

// ---------------------------------------------------------------------------
// resolveEffective
// ---------------------------------------------------------------------------

describe("resolveEffective", () => {
  it("uses shared values when override is empty", () => {
    const result = resolveEffective(
      { subject: "Mathematics", level: "Form 2" },
      { subject: "", level: "" },
    );
    expect(result).toEqual({ subject: "Mathematics", level: "Form 2" });
  });

  it("prefers non-empty individual override over shared", () => {
    const result = resolveEffective(
      { subject: "Mathematics", level: "Form 2" },
      { subject: "Physics", level: "" },
    );
    expect(result).toEqual({ subject: "Physics", level: "Form 2" });
  });

  it("uses both individual overrides when both non-empty", () => {
    const result = resolveEffective(
      { subject: "Mathematics", level: "Form 2" },
      { subject: "Physics", level: "Form 3" },
    );
    expect(result).toEqual({ subject: "Physics", level: "Form 3" });
  });

  it("trims whitespace: whitespace-only override falls back to shared", () => {
    const result = resolveEffective(
      { subject: "Mathematics", level: "Form 2" },
      { subject: "  ", level: "" },
    );
    expect(result).toEqual({ subject: "Mathematics", level: "Form 2" });
  });
});

// ---------------------------------------------------------------------------
// sharedDefaultsSchema
// ---------------------------------------------------------------------------

describe("sharedDefaultsSchema", () => {
  it("accepts valid shared defaults", () => {
    const result = sharedDefaultsSchema.safeParse({
      subject: "Math",
      level: "F2",
    });
    expect(result.success).toBe(true);
  });

  it("rejects empty subject", () => {
    const result = sharedDefaultsSchema.safeParse({
      subject: "",
      level: "F2",
    });
    expect(result.success).toBe(false);
  });

  it("rejects empty level", () => {
    const result = sharedDefaultsSchema.safeParse({
      subject: "Math",
      level: "",
    });
    expect(result.success).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// draftOverrideSchema
// ---------------------------------------------------------------------------

describe("draftOverrideSchema", () => {
  it("accepts empty strings (no override)", () => {
    const result = draftOverrideSchema.safeParse({
      subject: "",
      level: "",
    });
    expect(result.success).toBe(true);
  });

  it("accepts non-empty overrides", () => {
    const result = draftOverrideSchema.safeParse({
      subject: "Physics",
      level: "F3",
    });
    expect(result.success).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// buildDraftPayload
// ---------------------------------------------------------------------------

describe("buildDraftPayload", () => {
  it("maps draft fields to camelCase QuestionInput shape", () => {
    const payload = buildDraftPayload(
      stubDraft,
      { subject: "Mathematics", level: "Form 2" },
      2,
    );

    expect(payload.internalTitle).toBe("Q1");
    expect(payload.subject).toBe("Mathematics");
    expect(payload.level).toBe("Form 2");
    expect(payload.tags).toEqual(["algebra"]);
    expect(payload.sourceNote).toBeUndefined();
    expect(payload.marks).toBe(2);
    expect(payload.status).toBe("draft");
    // content should be normalized (same structure here)
    expect(payload.content.type).toBe("doc");
  });

  it("uses the explicitly provided numeric marks", () => {
    const payload = buildDraftPayload(
      stubDraft,
      { subject: "Math", level: "F2" },
      5,
    );
    expect(payload.marks).toBe(5);
  });

  it("preserves source_note when present", () => {
    const draft: QuestionIngestDraft = {
      ...stubDraft,
      source_note: "Past paper 2023",
    };
    const payload = buildDraftPayload(
      draft,
      { subject: "Math", level: "F2" },
      2,
    );
    expect(payload.sourceNote).toBe("Past paper 2023");
  });
});
