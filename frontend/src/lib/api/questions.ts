import { apiFetch } from "./client";
import type { QuestionContent } from "@/lib/validation/content";

export type QuestionStatus = "draft" | "ready";
export type Question = {
  id: string;
  workspace_id: string;
  internal_title: string;
  subject: string;
  level: string;
  tags_json: string[];
  source_note: string | null;
  content_json: QuestionContent;
  marks: string | number;
  status: QuestionStatus;
  created_at: string;
  updated_at: string;
};

export type QuestionInput = {
  internalTitle: string;
  subject: string;
  level: string;
  tags: string[];
  sourceNote?: string;
  content: QuestionContent;
  status: QuestionStatus;
};

function toPayload(input: QuestionInput) {
  return { internal_title: input.internalTitle, subject: input.subject, level: input.level, tags_json: input.tags, source_note: input.sourceNote || null, content_json: input.content, status: input.status };
}

export async function listQuestions(token: string): Promise<Question[]> {
  const response = await apiFetch<Question[] | { items: Question[] }>("/api/v1/questions", token);
  return Array.isArray(response) ? response : response.items;
}
export function createQuestion(token: string, input: QuestionInput) { return apiFetch<Question>("/api/v1/questions", token, { method: "POST", body: JSON.stringify(toPayload(input)) }); }
export function updateQuestion(token: string, id: string, input: QuestionInput) { return apiFetch<Question>(`/api/v1/questions/${encodeURIComponent(id)}`, token, { method: "PATCH", body: JSON.stringify(toPayload(input)) }); }

export type DeclaredMark = {
  value: string | number;
  raw_text: string;
  location: string;
};

export type QuestionIngestDraft = {
  internal_title: string;
  subject: string;
  level: string;
  tags_json: string[];
  source_note: string | null;
  content_json: QuestionContent;
  marks: string | number | null;
  declared_marks: DeclaredMark[];
  needs_review: boolean;
  validation_issues: string[];
  status: QuestionStatus;
};

export function ingestQuestions(
  token: string,
  source: { text?: string; file?: File },
): Promise<QuestionIngestDraft[]> {
  const body = new FormData();
  if (source.text !== undefined) body.set("text", source.text);
  if (source.file) body.set("file", source.file);
  return apiFetch<QuestionIngestDraft[]>("/api/v1/questions/ingest", token, { method: "POST", body });
}
