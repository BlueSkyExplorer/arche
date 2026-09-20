import type { AnswerSheetExport, DocumentMetadata } from "@/lib/api/answer-sheet-exports";
import type { AnsSheet, ExamImportSummary } from "@/lib/api/exam-imports";

export function canFormatAnswerSheet(item: Pick<ExamImportSummary, "import_type" | "status">): boolean {
  return item.import_type === "answer_sheet" && item.status === "completed";
}

export function canExportAnswerSheet(preview: AnswerSheetExport | null): boolean {
  return preview?.status === "succeeded" && preview.validation_json.valid;
}

export function metadataComplete(metadata: DocumentMetadata): boolean {
  return Object.values(metadata).every((value) => value.trim().length > 0);
}

export function answerSheetReviewReadOnly(status: string): boolean {
  return status === "completed";
}

export function warningsForDisplay(sheet: AnsSheet) {
  return sheet.warnings;
}
