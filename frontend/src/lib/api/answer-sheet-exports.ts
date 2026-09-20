import { apiDownload, apiFetch } from "./client";
import type { AnsSheet } from "./exam-imports";

export type DocumentMetadata = {
  school_name: string;
  academic_year: string;
  exam_name: string;
  level: string;
  subject: string;
  document_type: string;
};

export const FORMAT_METADATA_FIELDS: (keyof DocumentMetadata)[] = [
  "school_name",
  "academic_year",
  "exam_name",
  "level",
  "subject",
  "document_type",
];

export type RenderValidation = {
  valid: boolean;
  blocking_count: number;
  issues: { code: string; severity: "warning" | "blocking"; message: string; path: string }[];
  stats: {
    sections: number;
    mcq_items: number;
    question_nodes: number;
    leaves: number;
    paragraphs: number;
    tables: number;
    images: number;
  };
};

export type AnswerSheetExport = {
  id: string;
  exam_import_id: string;
  template_profile_id: string;
  template_version: number;
  reviewed_answer_sheet_snapshot: AnsSheet;
  template_config_snapshot: Record<string, unknown>;
  metadata_snapshot: DocumentMetadata;
  purpose: "preview" | "export";
  format: "docx";
  status: "succeeded" | "blocked" | "failed";
  error_message: string | null;
  validation_json: RenderValidation;
  created_at: string;
};

export type AnswerSheetPreview = {
  record: AnswerSheetExport;
  preview: {
    metadata: DocumentMetadata;
    answer_sheet: AnsSheet;
    validation: RenderValidation;
    template_version: number;
  };
};

function payload(templateId: string, metadata: DocumentMetadata) {
  return { template_profile_id: templateId, metadata };
}

export function previewAnswerSheet(
  token: string,
  importId: string,
  templateId: string,
  metadata: DocumentMetadata,
): Promise<AnswerSheetPreview> {
  return apiFetch(`/api/v1/exam-imports/${encodeURIComponent(importId)}/answer-sheet-preview`, token, {
    method: "POST",
    body: JSON.stringify(payload(templateId, metadata)),
  });
}

export function exportAnswerSheet(
  token: string,
  importId: string,
  templateId: string,
  metadata: DocumentMetadata,
): Promise<AnswerSheetExport> {
  return apiFetch(`/api/v1/exam-imports/${encodeURIComponent(importId)}/answer-sheet-exports`, token, {
    method: "POST",
    body: JSON.stringify(payload(templateId, metadata)),
  });
}

export function downloadAnswerSheetExport(token: string, exportId: string): Promise<Blob> {
  return apiDownload(`/api/v1/answer-sheet-exports/${encodeURIComponent(exportId)}/download`, token);
}
