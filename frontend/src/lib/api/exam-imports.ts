import { apiFetch } from "./client";

export type ValidationIssue = {
  code: string;
  severity: "info" | "warning" | "blocking";
  message: string;
  location: string;
  source_text?: string;
};

export type SourceEvidence = {
  page?: number | null;
  block_id?: string | null;
  bbox?: { x0: number; y0: number; x1: number; y1: number } | null;
  source_text?: string;
  confidence?: number;
};

export type AssetReference = {
  local_id: string;
  mime_type?: string | null;
  source_text?: string;
};

export type ContentBlock = {
  kind: string;
  text?: string | null;
  heading_level?: number | null;
  asset?: AssetReference | null;
  rows?: string[][] | null;
  source?: SourceEvidence;
};

export type QuestionNode = {
  label?: string | null;
  own_marks?: string | number | null;
  declared_marks?: { value: string | number; raw_text?: string }[];
  content?: ContentBlock[];
  children?: QuestionNode[];
  source?: SourceEvidence;
  confidence?: number;
};

export type ExamSection = {
  title?: string | null;
  questions?: QuestionNode[];
};

export type ExamDocument = {
  sections: ExamSection[];
  assets?: AssetReference[];
  subject?: string | null;
  level?: string | null;
  meta?: Record<string, unknown>;
};

export type ExamImportSummary = {
  id: string;
  source_filename: string;
  source_type: string;
  status: string;
  extractor_name: string | null;
  provider: string | null;
  model: string | null;
  fallback_occurred: boolean;
  needs_review: boolean;
  failure_message: string | null;
  validation_json: { issues: ValidationIssue[] } | null;
  created_at: string;
  updated_at: string;
};

export type ExamImportDetail = ExamImportSummary & {
  schema_version: string | null;
  blocks_json: { id: string; page?: number | null; kind: string; text?: string | null; order: number }[];
  extracted_document_json: ExamDocument | null;
  reviewed_document_json: ExamDocument | null;
  created_question_ids: string[];
  reviewed_at: string | null;
  completed_at: string | null;
};

export function listExamImports(token: string): Promise<ExamImportSummary[]> {
  return apiFetch<ExamImportSummary[]>("/api/v1/exam-imports", token);
}

export function createExamImport(token: string, file: File): Promise<ExamImportDetail> {
  const body = new FormData();
  body.set("file", file);
  return apiFetch<ExamImportDetail>("/api/v1/exam-imports", token, { method: "POST", body });
}

export function getExamImport(token: string, id: string): Promise<ExamImportDetail> {
  return apiFetch<ExamImportDetail>(`/api/v1/exam-imports/${encodeURIComponent(id)}`, token);
}

export function saveReviewed(token: string, id: string, reviewed: ExamDocument): Promise<ExamImportDetail> {
  return apiFetch<ExamImportDetail>(`/api/v1/exam-imports/${encodeURIComponent(id)}/reviewed`, token, {
    method: "PUT",
    body: JSON.stringify(reviewed),
  });
}

export function approveImport(token: string, id: string): Promise<ExamImportDetail> {
  return apiFetch<ExamImportDetail>(`/api/v1/exam-imports/${encodeURIComponent(id)}/approve`, token, {
    method: "POST",
  });
}
