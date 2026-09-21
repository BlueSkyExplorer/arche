import { describe, expect, it, vi } from "vitest";
import { FORMAT_METADATA_FIELDS, type AnswerSheetExport, type DocumentMetadata } from "./api/answer-sheet-exports";
import { fetchImportAsset } from "./api/exam-imports";
import {
  answerSheetReviewReadOnly,
  canExportAnswerSheet,
  canFormatAnswerSheet,
  metadataComplete,
  warningsForDisplay,
} from "./answer-sheet-format";

const metadata: DocumentMetadata = {
  school_name: "School",
  academic_year: "2026-2027",
  exam_name: "Final",
  level: "S4",
  subject: "Biology",
  document_type: "Answer key",
};

describe("answer-sheet format workflow", () => {
  it("shows Format only for completed answer sheets", () => {
    expect(canFormatAnswerSheet({ import_type: "answer_sheet", status: "completed" })).toBe(true);
    expect(canFormatAnswerSheet({ import_type: "answer_sheet", status: "ready" })).toBe(false);
    expect(canFormatAnswerSheet({ import_type: "question_paper", status: "completed" })).toBe(false);
  });

  it("requires the template metadata fields and complete values", () => {
    expect(FORMAT_METADATA_FIELDS).toEqual([
      "school_name",
      "academic_year",
      "exam_name",
      "level",
      "subject",
      "document_type",
    ]);
    expect(metadataComplete(metadata)).toBe(true);
    expect(metadataComplete({ ...metadata, subject: "" })).toBe(false);
  });

  it("enables export only after a valid succeeded preview", () => {
    const record = {
      status: "succeeded",
      validation_json: { valid: true },
    } as AnswerSheetExport;
    expect(canExportAnswerSheet(record)).toBe(true);
    expect(canExportAnswerSheet({ ...record, status: "blocked" })).toBe(false);
    expect(canExportAnswerSheet({ ...record, validation_json: { ...record.validation_json, valid: false } })).toBe(false);
    expect(canExportAnswerSheet(null)).toBe(false);
  });

  it("keeps completed review read-only and warnings visible", () => {
    const warning = { code: "declared_total_mismatch", message: "50 vs 51" };
    expect(answerSheetReviewReadOnly("completed")).toBe(true);
    expect(answerSheetReviewReadOnly("ready")).toBe(false);
    expect(warningsForDisplay({ title: "", sections: [], warnings: [warning] })).toEqual([warning]);
  });
});

describe("authenticated answer image", () => {
  it("fetches image bytes with the bearer token instead of a direct img URL", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(new Blob(["image"], { type: "image/png" }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const blob = await fetchImportAsset("secret-token", "import-id", "shape-0");
    expect(blob.type).toBe("image/png");
    const [, init] = fetchMock.mock.calls[0] as [URL, RequestInit];
    expect(new Headers(init.headers).get("Authorization")).toBe("Bearer secret-token");
    vi.unstubAllGlobals();
  });
});
